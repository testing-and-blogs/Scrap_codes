from django.test import TestCase, override_settings
from unittest.mock import patch
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet

from core.models import Project, Connection
from .factory import get_connector
from .postgres import PostgresConnector
from .mysql import MySqlConnector
from .base import BaseConnector

# A valid Fernet key generated for testing purposes
TEST_FERNET_KEY = Fernet.generate_key().decode()

@override_settings(DMIGRATE_FERNET_KEY=TEST_FERNET_KEY)
class ConnectorFactoryTest(TestCase):
    """
    Test suite for the connector factory.
    """
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        user = User.objects.create_user(username='testuser', password='password')
        project = Project.objects.create(name='Test Project', owner=user)
        cls.postgres_connection = Connection.objects.create(
            project=project, name="Test Postgres Conn", db_type=Connection.DbType.POSTGRES,
            host="pg_host", port=5432, username="pguser", dbname="pgdb", password="pgpassword"
        )
        cls.mysql_connection = Connection.objects.create(
            project=project, name="Test MySQL Conn", db_type=Connection.DbType.MYSQL,
            host="mysql_host", port=3306, username="mysqluser", dbname="mysqldb", password="mysqlpassword"
        )

    def test_factory_returns_postgres_connector(self):
        """
        Tests that the factory returns a PostgresConnector instance for 'postgres' db_type.
        """
        connector = get_connector(self.postgres_connection)
        self.assertIsInstance(connector, PostgresConnector)
        self.assertIsInstance(connector, BaseConnector)

    def test_factory_returns_mysql_connector(self):
        """
        Tests that the factory returns a MySqlConnector instance for 'mysql' db_type.
        """
        connector = get_connector(self.mysql_connection)
        self.assertIsInstance(connector, MySqlConnector)
        self.assertIsInstance(connector, BaseConnector)

    def test_factory_raises_value_error_for_unsupported_type(self):
        """
        Tests that the factory raises a ValueError for an unsupported db_type.
        """
        # Create a connection with a hypothetical unsupported type
        unsupported_connection = self.postgres_connection
        unsupported_connection.db_type = 'unsupported_db_type'

        with self.assertRaisesMessage(ValueError, "Unsupported database type: 'unsupported_db_type'"):
            get_connector(unsupported_connection)


class ConnectorImplementationTest(TestCase):
    """
    Test suite for the concrete connector implementations.
    """
    def setUp(self):
        """Set up common connection details for the tests."""
        self.connection_details = {
            'username': 'test_user',
            'password': 'test_password',
            'host': 'test_host',
            'port': 9999,
            'dbname': 'test_db'
        }

    @patch('connectors.postgres.create_engine')
    def test_postgres_connector_builds_correct_uri(self, mock_create_engine):
        """
        Tests that the PostgresConnector constructs the correct SQLAlchemy connection URI.
        """
        connector = PostgresConnector(self.connection_details)
        connector.get_engine()  # This should call create_engine

        expected_uri = "postgresql+psycopg2://test_user:test_password@test_host:9999/test_db"
        mock_create_engine.assert_called_once_with(expected_uri)

    @patch('connectors.mysql.create_engine')
    def test_mysql_connector_builds_correct_uri(self, mock_create_engine):
        """
        Tests that the MySqlConnector constructs the correct SQLAlchemy connection URI.
        """
        connector = MySqlConnector(self.connection_details)
        connector.get_engine()  # This should call create_engine

        expected_uri = "mysql+mysqlconnector://test_user:test_password@test_host:9999/test_db"
        mock_create_engine.assert_called_once_with(expected_uri)
