import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Project, Connection
from .models import MappingConfig, TableMapping, ColumnMapping
from .services import generate_ddl

User = get_user_model()

class MappingModelsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.project = Project.objects.create(name='Test Project', owner=cls.user)
        cls.source_conn = Connection.objects.create(project=cls.project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        cls.target_conn = Connection.objects.create(project=cls.project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')
        cls.mapping = MappingConfig.objects.create(
            project=cls.project, name='Test Mapping',
            source_connection=cls.source_conn, target_connection=cls.target_conn
        )
        cls.table_mapping = TableMapping.objects.create(
            mapping_config=cls.mapping, source_table_name='src_table', target_table_name='tgt_table'
        )

    def test_model_creation(self):
        self.assertEqual(MappingConfig.objects.count(), 1)
        self.assertEqual(TableMapping.objects.count(), 1)

        column_mapping = ColumnMapping.objects.create(
            table_mapping=self.table_mapping, source_column_name='src_col',
            target_column_name='tgt_col', target_data_type='INTEGER'
        )
        self.assertEqual(ColumnMapping.objects.count(), 1)
        self.assertEqual(str(self.mapping), 'Test Mapping')


class MappingAPIViewsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.project = Project.objects.create(name='Test Project', owner=cls.user)
        cls.source_conn = Connection.objects.create(project=cls.project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        cls.target_conn = Connection.objects.create(project=cls.project, name='Tgt', db_type='postgres', host='h', port=1, username='u', dbname='d')

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='password')
        self.valid_payload = {
            "name": "My API Mapping",
            "project_id": self.project.id,
            "source_connection_id": self.source_conn.id,
            "target_connection_id": self.target_conn.id,
            "tables": [{
                "source_table_name": "src_customers",
                "target_table_name": "tgt_customers",
                "include_in_migration": True,
                "columns": [{
                    "source_column_name": "id", "target_column_name": "customer_id",
                    "target_data_type": "SERIAL PRIMARY KEY", "is_ignored": False
                }]
            }]
        }

    def test_save_mapping_config(self):
        url = reverse('ui:save_mapping_config')
        response = self.client.post(url, data=json.dumps(self.valid_payload), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.assertTrue(MappingConfig.objects.filter(name="My API Mapping").exists())
        self.assertEqual(TableMapping.objects.count(), 1)
        self.assertEqual(ColumnMapping.objects.count(), 1)

    def test_load_mapping_config(self):
        # First, save a mapping
        save_url = reverse('ui:save_mapping_config')
        self.client.post(save_url, data=json.dumps(self.valid_payload), content_type='application/json')
        mapping_id = MappingConfig.objects.get(name="My API Mapping").id

        # Then, load it
        load_url = reverse('ui:load_mapping_config', args=[mapping_id])
        response = self.client.get(load_url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], "My API Mapping")
        self.assertEqual(len(data['tables']), 1)
        self.assertEqual(data['tables'][0]['columns'][0]['target_column_name'], 'customer_id')


class DDLGenerationTest(TestCase):

    def setUp(self):
        user = User.objects.create_user(username='testuser', password='password')
        project = Project.objects.create(name='Test Project', owner=user)
        source_conn = Connection.objects.create(project=project, name='Src', db_type='postgres', host='h', port=1, username='u', dbname='d')
        target_conn_pg = Connection.objects.create(project=project, name='Tgt PG', db_type='postgres', host='h', port=1, username='u', dbname='d')

        self.mapping_pg = MappingConfig.objects.create(
            project=project, name='Test Mapping PG',
            source_connection=source_conn, target_connection=target_conn_pg
        )
        table_mapping = TableMapping.objects.create(
            mapping_config=self.mapping_pg, source_table_name='t1', target_table_name='target_t1'
        )
        ColumnMapping.objects.create(table_mapping=table_mapping, source_column_name='c1', target_column_name='new_c1', target_data_type='INTEGER')
        ColumnMapping.objects.create(table_mapping=table_mapping, source_column_name='c2', target_column_name='new_c2', target_data_type='VARCHAR(100)')
        # This one should be ignored
        ColumnMapping.objects.create(table_mapping=table_mapping, source_column_name='c3', target_column_name='new_c3', target_data_type='BOOLEAN', is_ignored=True)

    def test_generate_ddl_postgres(self):
        ddl = generate_ddl(self.mapping_pg)
        self.assertIn('CREATE TABLE IF NOT EXISTS "target_t1"', ddl)
        self.assertIn('"new_c1" INTEGER', ddl)
        self.assertIn('"new_c2" VARCHAR(100)', ddl)
        self.assertNotIn('new_c3', ddl)
