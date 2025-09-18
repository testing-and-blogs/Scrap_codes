from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet, InvalidToken

from .models import Project, Connection

# A valid Fernet key generated for testing purposes
TEST_FERNET_KEY = Fernet.generate_key().decode()

@override_settings(DMIGRATE_FERNET_KEY=TEST_FERNET_KEY)
class ConnectionModelTest(TestCase):
    """
    Test suite for the Connection model, focusing on password encryption.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up non-modified objects used by all test methods."""
        User = get_user_model()
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.project = Project.objects.create(name='Test Project', owner=cls.user)

    def test_password_encryption_and_decryption(self):
        """
        Tests that a password is correctly encrypted when set and decrypted when get.
        """
        raw_password = "my_super_secret_password_123"
        connection = Connection(
            project=self.project,
            name="Test PG Connection",
            db_type=Connection.DbType.POSTGRES,
            host="localhost",
            port=5432,
            username="pguser",
            dbname="pgdb"
        )

        # Set the password using the property setter
        connection.password = raw_password
        connection.save()

        # Assert that the stored value is not the raw password
        self.assertIsNotNone(connection.password_encrypted)
        self.assertNotEqual(connection.password_encrypted, raw_password)

        # Retrieve the same object from the database
        retrieved_connection = Connection.objects.get(pk=connection.pk)

        # Assert that the decrypted password matches the original
        self.assertEqual(retrieved_connection.get_password(), raw_password)
        # Assert that the property getter also works
        self.assertEqual(retrieved_connection.password, raw_password)

    def test_empty_password_is_handled(self):
        """
        Tests that setting an empty or None password results in an empty
        encrypted field and None when decrypted.
        """
        connection = Connection(
            project=self.project, name="Test Empty Password",
            db_type='postgres', host='h', port=5432, username='u', dbname='d'
        )

        # Test with empty string
        connection.password = ""
        connection.save()
        self.assertEqual(connection.password_encrypted, "")
        self.assertIsNone(connection.get_password())

        # Test with None
        # We need a new instance as the previous one is already saved
        connection2 = Connection(
            project=self.project, name="Test Empty Password 2",
            db_type='postgres', host='h', port=5432, username='u', dbname='d'
        )
        connection2.password = None
        connection2.save()
        self.assertEqual(connection2.password_encrypted, "")
        self.assertIsNone(connection2.get_password())

    @override_settings(DMIGRATE_FERNET_KEY=None)
    def test_fernet_key_not_set_raises_value_error(self):
        """
        Tests that a ValueError is raised if DMIGRATE_FERNET_KEY is missing.
        """
        connection = Connection(project=self.project, name="Conn No Key")

        # Test setting the password
        with self.assertRaisesMessage(ValueError, "DMIGRATE_FERNET_KEY environment variable is not set."):
            connection.password = "a_password"

        # Test getting the password
        connection.password_encrypted = "some_encrypted_data"
        with self.assertRaisesMessage(ValueError, "DMIGRATE_FERNET_KEY environment variable is not set."):
            _ = connection.password

    def test_get_password_with_invalid_token(self):
        """
        Tests that get_password returns None if the token is invalid or corrupted.
        """
        connection = Connection(
            project=self.project, name="Conn Invalid Token",
            db_type='postgres', host='h', port=5432, username='u', dbname='d'
        )
        connection.password_encrypted = "this_is_not_a_valid_fernet_token"
        connection.save()

        # The get_password method should catch the InvalidToken exception and return None
        self.assertIsNone(connection.get_password())
