from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from core.models import Project, Connection
from mapping.models import MappingConfig, TableMapping, ColumnMapping
from .models import MigrationJob, MigrationChunk
from .tasks import start_migration_job, process_migration_chunk

User = get_user_model()

class JobModelsTest(TestCase):

    def test_job_model_creation(self):
        user = User.objects.create_user(username='testuser', password='password')
        project = Project.objects.create(name='Test Project', owner=user)
        source_conn = Connection.objects.create(project=project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        target_conn = Connection.objects.create(project=project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')
        mapping = MappingConfig.objects.create(
            project=project, name='Test Mapping',
            source_connection=source_conn, target_connection=target_conn
        )
        job = MigrationJob.objects.create(mapping_config=mapping)
        self.assertEqual(job.status, MigrationJob.Status.PENDING)
        self.assertEqual(MigrationJob.objects.count(), 1)


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
