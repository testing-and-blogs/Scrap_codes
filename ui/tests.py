from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import json

from core.models import Project, Connection
from mapping.models import MappingConfig, SchemaSnapshot
from jobs.models import SyncSchedule

User = get_user_model()

class UIDashboardViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        Project.objects.create(name='Test Project', owner=cls.user)

    def setUp(self):
        self.client = Client()

    def test_dashboard_unauthenticated_redirects(self):
        """Tests that an unauthenticated user is redirected to the login page."""
        response = self.client.get(reverse('ui:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_authenticated_user_sees_projects(self):
        """Tests that an authenticated user can see their projects."""
        self.client.login(username='testuser', password='password')
        response = self.client.get(reverse('ui:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ui/dashboard.html')
        self.assertContains(response, 'Test Project')


class UIProjectDetailViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(username='user1', password='password')
        cls.user2 = User.objects.create_user(username='user2', password='password')
        cls.project1 = Project.objects.create(name='User1 Project', owner=cls.user1)

    def setUp(self):
        self.client = Client()
        self.client.login(username='user1', password='password')

    def test_project_detail_loads_for_owner(self):
        """Tests that the project owner can access the detail view."""
        response = self.client.get(reverse('ui:project_detail', args=[self.project1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ui/project_detail.html')
        self.assertContains(response, 'User1 Project')

    def test_project_detail_returns_404_for_other_user(self):
        """Tests that a user cannot access another user's project details."""
        self.client.login(username='user2', password='password')
        response = self.client.get(reverse('ui:project_detail', args=[self.project1.id]))
        self.assertEqual(response.status_code, 404)


class UIConnectionAPIViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(username='user1', password='password')
        cls.user2 = User.objects.create_user(username='user2', password='password')
        project1 = Project.objects.create(name='User1 Project', owner=cls.user1)
        cls.conn1 = Connection.objects.create(
            project=project1, name='User1 Conn', db_type='postgres',
            host='h', port=5432, username='u', dbname='db'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='user1', password='password')

    @patch('ui.views.get_connector')
    def test_test_connection_success(self, mock_get_connector):
        """Tests the test_connection endpoint on success."""
        # Configure the mock
        mock_connector = MagicMock()
        mock_connector.test_connection.return_value = (True, 'Connection successful.')
        mock_get_connector.return_value = mock_connector

        url = reverse('ui:test_connection', args=[self.conn1.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Connection successful.')
        mock_get_connector.assert_called_once()
        mock_connector.test_connection.assert_called_once()

    @patch('ui.views.get_connector')
    def test_test_connection_failure(self, mock_get_connector):
        """Tests the test_connection endpoint on failure."""
        mock_connector = MagicMock()
        mock_connector.test_connection.return_value = (False, 'Connection failed.')
        mock_get_connector.return_value = mock_connector

        url = reverse('ui:test_connection', args=[self.conn1.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], 'Connection failed.')

    @patch('ui.views.get_connector')
    def test_discover_schema_success(self, mock_get_connector):
        """Tests the discover_schema endpoint on success."""
        mock_connector = MagicMock()
        mock_connector.discover_schema.return_value = {'tables': ['table1']}
        mock_get_connector.return_value = mock_connector

        url = reverse('ui:discover_schema', args=[self.conn1.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(SchemaSnapshot.objects.filter(connection=self.conn1).exists())
        snapshot = SchemaSnapshot.objects.get(connection=self.conn1)
        self.assertEqual(snapshot.schema, {'tables': ['table1']})

    def test_api_returns_404_for_other_user(self):
        """Tests that API endpoints return 404 for connections not owned by the user."""
        self.client.login(username='user2', password='password')

        test_url = reverse('ui:test_connection', args=[self.conn1.id])
        discover_url = reverse('ui:discover_schema', args=[self.conn1.id])

        response_test = self.client.post(test_url)
        response_discover = self.client.post(discover_url)

        self.assertEqual(response_test.status_code, 404)
        self.assertEqual(response_discover.status_code, 404)


class UISyncViewTest(TestCase):

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
