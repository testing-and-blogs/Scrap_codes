from django.test import TestCase, Client
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from core.models import Project, Connection
from mapping.models import MappingConfig, TableMapping, ColumnMapping
from .models import MigrationJob, MigrationChunk, SyncSchedule, SyncJob
from .tasks import start_migration_job, process_migration_chunk, schedule_due_syncs, run_sync_job
from .admin import force_stop_jobs

User = get_user_model()

class JobModelsTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(name='Test Project', owner=self.user)
        self.source_conn = Connection.objects.create(project=self.project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        self.target_conn = Connection.objects.create(project=self.project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')
        self.mapping = MappingConfig.objects.create(
            project=self.project, name='Test Mapping',
            source_connection=self.source_conn, target_connection=self.target_conn
        )

    def test_job_model_creation(self):
        job = MigrationJob.objects.create(mapping_config=self.mapping)
        self.assertEqual(job.status, MigrationJob.Status.PENDING)
        self.assertEqual(MigrationJob.objects.count(), 1)

    def test_sync_schedule_model_creation(self):
        schedule = SyncSchedule.objects.create(
            mapping_config=self.mapping,
            frequency=SyncSchedule.Frequency.DAILY,
            sync_key_column='updated_at'
        )
        self.assertTrue(schedule.is_active)
        self.assertEqual(SyncSchedule.objects.count(), 1)


class JobCeleryTasksTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(username='testuser', password='password')
        project = Project.objects.create(name='Test Project', owner=user)
        source_conn = Connection.objects.create(project=project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        target_conn = Connection.objects.create(project=project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')
        cls.mapping = MappingConfig.objects.create(
            project=project, name='Test Mapping',
            source_connection=source_conn, target_connection=target_conn
        )
        cls.table_map = TableMapping.objects.create(mapping_config=cls.mapping, source_table_name='t1', target_table_name='t1_tgt')

    @patch('jobs.tasks.process_migration_chunk.delay')
    @patch('jobs.tasks.get_connector')
    def test_start_migration_job_task(self, mock_get_connector, mock_process_chunk):
        # Mock the connector to return a row count
        mock_connector = MagicMock()
        mock_connector.get_row_count.return_value = 10000
        mock_get_connector.return_value = mock_connector

        job = MigrationJob.objects.create(mapping_config=self.mapping)
        start_migration_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, MigrationJob.Status.RUNNING)
        # 10000 rows / 5000 chunk size = 2 chunks
        self.assertEqual(job.chunks.count(), 2)
        self.assertEqual(mock_process_chunk.call_count, 2)
        mock_connector.get_row_count.assert_called_once_with('t1')

    @patch('jobs.tasks.get_connector')
    def test_process_migration_chunk_task(self, mock_get_connector):
        # Mock the connectors and engines
        mock_source_engine = MagicMock()
        mock_target_engine = MagicMock()
        mock_source_conn = MagicMock()
        mock_target_conn = MagicMock()

        # Simulate the context managers
        mock_source_engine.connect.return_value.__enter__.return_value = mock_source_conn
        mock_target_engine.connect.return_value.__enter__.return_value = mock_target_conn
        mock_target_conn.begin.return_value.__enter__.return_value = None # Transaction

        # Simulate the data returned from the source
        mock_source_data = [{'id': 1, 'name': 'test'}]
        # Simulate SQLAlchemy's RowProxy by adding _asdict()
        mock_row = MagicMock()
        mock_row._asdict.return_value = mock_source_data[0]
        mock_source_conn.execute.return_value = [mock_row]

        # Setup mock connectors
        mock_connector_instance = MagicMock()
        mock_connector_instance.get_engine.side_effect = [mock_source_engine, mock_target_engine]
        mock_get_connector.return_value = mock_connector_instance

        job = MigrationJob.objects.create(mapping_config=self.mapping)
        chunk = MigrationChunk.objects.create(job=job, table_mapping=self.table_map, offset=0, limit=5000)
        ColumnMapping.objects.create(table_mapping=self.table_map, source_column_name='id', target_column_name='new_id', target_data_type='INT')
        ColumnMapping.objects.create(table_mapping=self.table_map, source_column_name='name', target_column_name='new_name', target_data_type='TEXT')

        process_migration_chunk(chunk.id)

        chunk.refresh_from_db()
        self.assertEqual(chunk.status, MigrationJob.Status.SUCCESS)
        self.assertEqual(chunk.processed_rows, 1)
        # Check that the target connection executed an insert
        self.assertTrue(mock_target_conn.execute.called)

    @patch('jobs.tasks.run_sync_job.delay')
    @patch('django.utils.timezone.now')
    def test_schedule_due_syncs_task(self, mock_now, mock_run_sync):
        # Set a fixed point in time
        fixed_time = timezone.make_aware(timezone.datetime(2023, 1, 1, 12, 0, 0))
        mock_now.return_value = fixed_time

        # Create a schedule that is due
        due_schedule = SyncSchedule.objects.create(
            mapping_config=self.mapping, frequency=SyncSchedule.Frequency.HOURLY,
            sync_key_column='id', is_active=True
        )
        # Set its last update time to be more than an hour ago relative to the fixed time
        # We use .update() to bypass the auto_now=True behavior of the save() method.
        SyncSchedule.objects.filter(pk=due_schedule.pk).update(updated_at=fixed_time - timedelta(hours=2))

        # Create a schedule that is not due, with a new mapping
        mapping2 = MappingConfig.objects.create(project=self.mapping.project, name='Mapping 2', source_connection=self.mapping.source_connection, target_connection=self.mapping.target_connection)
        not_due_schedule = SyncSchedule.objects.create(
            mapping_config=mapping2, frequency=SyncSchedule.Frequency.DAILY,
            sync_key_column='id', is_active=True
        ) # updated_at is now, so it's not due

        # Create a schedule that is due but has a job already running
        mapping3 = MappingConfig.objects.create(project=self.mapping.project, name='Mapping 3', source_connection=self.mapping.source_connection, target_connection=self.mapping.target_connection)
        running_schedule = SyncSchedule.objects.create(
            mapping_config=mapping3, frequency=SyncSchedule.Frequency.HOURLY,
            sync_key_column='id', is_active=True
        )
        running_schedule.updated_at = fixed_time - timedelta(hours=2) # This line is not strictly needed but good for clarity
        SyncSchedule.objects.filter(pk=running_schedule.pk).update(updated_at=fixed_time - timedelta(hours=2))
        SyncJob.objects.create(sync_schedule=running_schedule, status=MigrationJob.Status.RUNNING)

        schedule_due_syncs()

        # Assert that only the due schedule was queued and a SyncJob was created for it
        self.assertEqual(SyncJob.objects.count(), 2) # The one we created + the new one
        self.assertTrue(SyncJob.objects.filter(sync_schedule=due_schedule).exists())
        new_job = SyncJob.objects.get(sync_schedule=due_schedule)
        mock_run_sync.assert_called_once_with(new_job.id)

    @patch('jobs.tasks.get_connector')
    def test_run_sync_job_task(self, mock_get_connector):
        # Mock connector and source data
        mock_connector = MagicMock()
        mock_source_engine = MagicMock()
        mock_source_conn = MagicMock()
        mock_source_engine.connect.return_value.__enter__.return_value = mock_source_conn

        mock_row = MagicMock()
        mock_row._asdict.return_value = {'id': 101, 'name': 'new_user'}
        mock_source_conn.execute.return_value = [mock_row]

        mock_connector.get_engine.return_value = mock_source_engine
        mock_get_connector.return_value = mock_connector

        # Setup schedule and mapping
        schedule = SyncSchedule.objects.create(
            mapping_config=self.mapping, frequency=SyncSchedule.Frequency.HOURLY,
            sync_key_column='id', is_active=True, last_sync_value='100'
        )
        ColumnMapping.objects.create(table_mapping=self.table_map, source_column_name='id', target_column_name='id', is_primary_key=True)

        # Create a SyncJob for the task to run
        job = SyncJob.objects.create(sync_schedule=schedule)

        run_sync_job(job.id)

        schedule.refresh_from_db()
        job.refresh_from_db()

        # The new max value of the sync key 'id' should be '101'
        self.assertEqual(schedule.last_sync_value, '101')
        # The upsert method on the target connector should have been called
        self.assertTrue(mock_connector.upsert.called)
        # The job should be marked as SUCCESS
        self.assertEqual(job.status, MigrationJob.Status.SUCCESS)


class JobViewsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        project = Project.objects.create(name='Test Project', owner=cls.user)
        source_conn = Connection.objects.create(project=project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        target_conn = Connection.objects.create(project=project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')
        cls.mapping = MappingConfig.objects.create(
            project=project, name='Test Mapping',
            source_connection=source_conn, target_connection=target_conn
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='password')

    @patch('ui.views.start_migration_job.delay')
    def test_start_migration_view(self, mock_start_job):
        url = reverse('ui:start_migration', args=[self.mapping.id])
        response = self.client.post(url)

        self.assertEqual(MigrationJob.objects.count(), 1)
        job = MigrationJob.objects.first()
        mock_start_job.assert_called_once_with(job.id)
        self.assertRedirects(response, reverse('ui:job_detail', args=[job.id]))

    def test_job_detail_view(self):
        job = MigrationJob.objects.create(mapping_config=self.mapping)
        url = reverse('ui:job_detail', args=[job.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ui/job_detail.html')
        self.assertContains(response, f"Job #{job.id} Details")

    def test_save_sync_schedule_view(self):
        url = reverse('ui:save_sync_schedule', args=[self.mapping.id])
        post_data = {
            'is_active': 'on',
            'frequency': SyncSchedule.Frequency.DAILY,
            'sync_key_column': 'modified_date'
        }
        response = self.client.post(url, data=post_data)

        self.assertRedirects(response, reverse('ui:project_detail', args=[self.mapping.project.id]))
        self.assertTrue(SyncSchedule.objects.filter(mapping_config=self.mapping).exists())
        schedule = SyncSchedule.objects.get(mapping_config=self.mapping)
        self.assertTrue(schedule.is_active)
        self.assertEqual(schedule.frequency, SyncSchedule.Frequency.DAILY)
        self.assertEqual(schedule.sync_key_column, 'modified_date')


class AdminActionsTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        project = Project.objects.create(name='Test Project', owner=self.user)
        source_conn = Connection.objects.create(project=project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        target_conn = Connection.objects.create(project=project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')
        mapping = MappingConfig.objects.create(
            project=project, name='Test Mapping',
            source_connection=source_conn, target_connection=target_conn
        )
        self.job1 = MigrationJob.objects.create(mapping_config=mapping, status=MigrationJob.Status.RUNNING)
        self.job2 = MigrationJob.objects.create(mapping_config=mapping, status=MigrationJob.Status.PENDING)

    def test_force_stop_jobs_admin_action(self):
        queryset = MigrationJob.objects.filter(id__in=[self.job1.id, self.job2.id])

        # Mock the model admin and request
        modeladmin = MagicMock()
        request = MagicMock()

        force_stop_jobs(modeladmin, request, queryset)

        self.job1.refresh_from_db()
        self.job2.refresh_from_db()

        self.assertEqual(self.job1.status, MigrationJob.Status.FAILED)
        self.assertEqual(self.job2.status, MigrationJob.Status.FAILED)
        modeladmin.message_user.assert_called_once()
