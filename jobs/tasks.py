import time
from celery import shared_task
from django.utils import timezone
from sqlalchemy import create_engine, text, Table, MetaData
from datetime import timedelta

from .models import MigrationJob, MigrationChunk, SyncSchedule, SyncJob
from connectors.factory import get_connector

CHUNK_SIZE = 5000  # Rows per chunk

@shared_task
def process_migration_chunk(chunk_id: int):
    """
    Celery task to process a single chunk of a migration job.
    This is the core ETL worker.
    """
    try:
        chunk = MigrationChunk.objects.select_related(
            'job__mapping_config__source_connection',
            'job__mapping_config__target_connection',
            'table_mapping'
        ).prefetch_related(
            'table_mapping__column_mappings'
        ).get(pk=chunk_id)

        chunk.status = MigrationJob.Status.RUNNING
        chunk.save()

        source_conn = get_connector(chunk.job.mapping_config.source_connection)
        target_conn = get_connector(chunk.job.mapping_config.target_connection)

        source_engine = source_conn.get_engine()
        target_engine = target_conn.get_engine()

        # E-T-L
        with source_engine.connect() as s_conn, target_engine.connect() as t_conn, t_conn.begin():
            # Extract
            # Note: This simple offset-based pagination can be slow on large tables.
            # Keyset pagination would be more performant.
            query = text(f'SELECT * FROM "{chunk.table_mapping.source_table_name}" LIMIT {chunk.limit} OFFSET {chunk.offset}')
            source_data = s_conn.execute(query)

            # Transform
            transformed_data = []
            column_mappings = chunk.table_mapping.column_mappings.filter(is_ignored=False)

            for row in source_data:
                row_dict = row._asdict()
                new_row = {}
                for col_map in column_mappings:
                    if col_map.source_column_name in row_dict:
                        new_row[col_map.target_column_name] = row_dict[col_map.source_column_name]
                transformed_data.append(new_row)

            # Load
            if transformed_data:
                target_table_name = chunk.table_mapping.target_table_name

                # We construct the INSERT statement manually to avoid database reflection
                # with mock engines in tests. Using named placeholders is safe.
                keys = transformed_data[0].keys()
                columns_str = ", ".join([f'"{k}"' for k in keys])
                values_placeholders = ", ".join([f":{k}" for k in keys])

                insert_stmt = text(f'INSERT INTO "{target_table_name}" ({columns_str}) VALUES ({values_placeholders})')

                t_conn.execute(insert_stmt, transformed_data)

            chunk.processed_rows = len(transformed_data)
            chunk.status = MigrationJob.Status.SUCCESS

    except Exception as e:
        chunk.status = MigrationJob.Status.FAILED
        chunk.error_message = str(e)

        # Pause the parent job if a chunk fails
        chunk.job.status = MigrationJob.Status.PAUSED
        chunk.job.error_message = f"Job paused due to failure in chunk {chunk.id}: {e}"
        chunk.job.save()

    finally:
        chunk.finished_at = timezone.now()
        chunk.save()


@shared_task
def start_migration_job(job_id: int):
    """
    Celery task to initialize a migration job and create all the necessary
    chunk sub-tasks.
    """
    job = MigrationJob.objects.get(pk=job_id)
    job.status = MigrationJob.Status.RUNNING
    job.save()

    source_conn = get_connector(job.mapping_config.source_connection)

    try:
        for table_map in job.mapping_config.table_mappings.filter(include_in_migration=True):
            total_rows = source_conn.get_row_count(table_map.source_table_name)

            offset = 0
            while offset < total_rows:
                chunk = MigrationChunk.objects.create(
                    job=job,
                    table_mapping=table_map,
                    offset=offset,
                    limit=CHUNK_SIZE
                )
                process_migration_chunk.delay(chunk.id)
                offset += CHUNK_SIZE

        # A more robust implementation would monitor chunk statuses and mark
        # the job as SUCCESS only when all chunks are successful.
        # For now, we assume success after dispatching. This is a simplification.
        # job.status = MigrationJob.Status.SUCCESS
        # job.finished_at = timezone.now()

    except Exception as e:
        job.status = MigrationJob.Status.FAILED
        job.error_message = str(e)
        job.finished_at = timezone.now()

    finally:
        job.save()


@shared_task
def run_sync_job(sync_job_id: int):
    """
    Celery task to run a single data synchronization job based on a schedule.
    """
    job = SyncJob.objects.select_related(
        'sync_schedule__mapping_config__source_connection',
        'sync_schedule__mapping_config__target_connection',
    ).get(pk=sync_job_id)

    job.status = MigrationJob.Status.RUNNING
    job.save()

    schedule = job.sync_schedule
    source_conn = get_connector(schedule.mapping_config.source_connection)
    target_conn = get_connector(schedule.mapping_config.target_connection)
    source_engine = source_conn.get_engine()

    try:
        new_max_sync_value = schedule.last_sync_value

        with source_engine.connect() as s_conn:
            for table_map in schedule.mapping_config.table_mappings.prefetch_related('column_mappings').filter(include_in_migration=True):

                # Build the incremental query
                query_str = f'SELECT * FROM "{table_map.source_table_name}"'
                params = {}
                if schedule.last_sync_value:
                    # Note: Assumes sync_key is a sortable type (numeric, timestamp, etc.)
                    query_str += f' WHERE "{schedule.sync_key_column}" > :last_value'
                    params['last_value'] = schedule.last_sync_value
                query_str += f' ORDER BY "{schedule.sync_key_column}"'

                source_data = s_conn.execute(text(query_str), params)

                # Transform
                transformed_data = []
                column_mappings = table_map.column_mappings.filter(is_ignored=False)

                for row in source_data:
                    row_dict = row._asdict()
                    new_row = {}
                    for col_map in column_mappings:
                        if col_map.source_column_name in row_dict:
                            new_row[col_map.target_column_name] = row_dict[col_map.source_column_name]
                    transformed_data.append(new_row)

                    # Track the max value of the sync key in this batch
                    current_sync_value = str(row_dict[schedule.sync_key_column])
                    if new_max_sync_value is None or current_sync_value > new_max_sync_value:
                        new_max_sync_value = current_sync_value

                # Load (Upsert)
                if transformed_data:
                    pk_col_map = table_map.column_mappings.filter(is_primary_key=True).first()
                    if not pk_col_map:
                        raise ValueError(f"No primary key defined in mapping for target table {table_map.target_table_name}")

                    target_conn.upsert(table_map.target_table_name, transformed_data, pk_col_map.target_column_name)

        # Update checkpoint on success
        schedule.last_sync_value = new_max_sync_value
        schedule.updated_at = timezone.now()
        schedule.save()

        job.status = MigrationJob.Status.SUCCESS
        job.finished_at = timezone.now()
        job.save()

    except Exception as e:
        job.status = MigrationJob.Status.FAILED
        job.error_message = str(e)
        job.finished_at = timezone.now()
        job.save()


@shared_task
def schedule_due_syncs():
    """
    Celery Beat task that runs periodically to check for and queue due sync jobs.
    """
    now = timezone.now()
    active_schedules = SyncSchedule.objects.filter(is_active=True)

    for schedule in active_schedules:
        # Prevent queueing a new job if one is already running for this schedule
        if schedule.sync_jobs.filter(status__in=[MigrationJob.Status.RUNNING, MigrationJob.Status.PENDING]).exists():
            continue

        delta = None
        if schedule.frequency == SyncSchedule.Frequency.HOURLY:
            delta = timedelta(hours=1)
        elif schedule.frequency == SyncSchedule.Frequency.DAILY:
            delta = timedelta(days=1)
        elif schedule.frequency == SyncSchedule.Frequency.WEEKLY:
            delta = timedelta(weeks=1)

        if delta and (now - schedule.updated_at) > delta:
            job = SyncJob.objects.create(sync_schedule=schedule)
            run_sync_job.delay(job.id)
