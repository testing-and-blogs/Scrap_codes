## Developer Guide

### How to Rotate the Encryption Key

Rotating the `DMIGRATE_FERNET_KEY` is a sensitive operation that must be done carefully to avoid locking yourself out of existing connection credentials. This process requires creating a temporary management command to re-encrypt the data.

**High-Level Steps:**

1.  **Back up your database.**
2.  Add the new key to your environment (e.g., `NEW_DMIGRATE_FERNET_KEY`) but keep the old key active (`DMIGRATE_FERNET_KEY`).
3.  Create a Django management command (`reencrypt_passwords.py`).
4.  Inside the command, load all `Connection` objects. For each one, decrypt its `password_encrypted` field using the old key and re-encrypt it using the new key.
5.  Run the management command: `docker-compose exec app python manage.py reencrypt_passwords`.
6.  Once all passwords are re-encrypted, update the `DMIGRATE_FERNET_KEY` in your `.env` file to the new key's value and remove the temporary `NEW_DMIGRATE_FERNET_KEY` variable.
7.  Restart the application services.

### How to Add a New Connector

The application is designed to be easily extended with new connectors. To add support for a new database (e.g., SQLite):

1.  **Create a new connector class** in a new file, e.g., `connectors/sqlite.py`.
    ```python
    # connectors/sqlite.py
    from .base import BaseConnector

    class SqliteConnector(BaseConnector):
        # ... implement the abstract methods ...
        def get_engine(self):
            # ...
        def test_connection(self):
            # ...
        def discover_schema(self):
            # ...
    ```
2.  **Update the `Connection` model** in `core/models.py` to include the new database type in the `DbType` choices.
    ```python
    # core/models.py
    class Connection(models.Model):
        class DbType(models.TextChoices):
            POSTGRES = 'postgres', 'PostgreSQL'
            MYSQL = 'mysql', 'MySQL'
            SQLITE = 'sqlite', 'SQLite' # Add new type here
        # ...
    ```
3.  **Update the connector factory** in `connectors/factory.py` to recognize the new type and return your new connector instance.
    ```python
    # connectors/factory.py
    from .sqlite import SqliteConnector # Import new connector

    def get_connector(connection: Connection) -> BaseConnector:
        # ...
        if connection.db_type == Connection.DbType.SQLITE:
            return SqliteConnector(connection_details)
        # ...
    ```
4.  **Install any required drivers.** If your new connector requires a Python package (e.g., `db-driver`), add it to `requirements.txt`.
5.  **Write tests** for your new connector in `connectors/tests.py`.
