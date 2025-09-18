import time
from celery import shared_task
from django.utils import timezone
from sqlalchemy import create_engine, text

from .models import MigrationJob, MigrationChunk
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
                # This is a simplified insert. A real implementation would need to handle
                # upserts, different data types, and use a more robust bulk insert method.
                # For now, we assume the target table is empty and types match.
                target_table = chunk.table_mapping.target_table_name

                # A more robust way would be to use SQLAlchemy's Table object and `table.insert()`
                # but for simplicity, we construct the insert statement.
                keys = transformed_data[0].keys()
                columns_str = ", ".join([f'"{k}"' for k in keys])
                values_placeholders = ", ".join([f":{k}" for k in keys])
                insert_stmt = text(f'INSERT INTO "{target_table}" ({columns_str}) VALUES ({values_placeholders})')

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
