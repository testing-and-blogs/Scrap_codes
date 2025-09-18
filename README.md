# Data Migration & Sync Service

This project is a Django-based, plugin-enabled Data Migration & Sync service. It allows users to connect to multiple database engines, map schemas, run full data migrations, and schedule and monitor data synchronization jobs.

This repository contains the foundational implementation ("Sprint 0") which includes the core application structure, connection management, and schema discovery.

## Features (Sprint 0)

*   **Dockerized Environment**: The entire application stack (Django, PostgreSQL, Redis, Celery) is managed via Docker and Docker Compose for easy local setup.
*   **Modular & Extensible Architecture**: The project is structured into logical Django apps (`core`, `connectors`, `mapping`, etc.) and features a plugin-based system for database connectors.
*   **Secure Connection Management**: Users can create and manage connections to source/target databases. Credentials are fully encrypted at rest using Fernet.
*   **Connection Testing**: An API endpoint allows users to test database connectivity and credentials before proceeding.
*   **Schema Discovery**: The application can introspect a connected database and display its schema (tables, columns, types) in the UI.
*   **Basic UI**: A user dashboard for listing projects and a project detail page for managing connections and viewing schemas.

---
## Prerequisites

Before you begin, ensure you have the following installed on your system:
*   [Docker](https://docs.docker.com/get-docker/)
*   [Docker Compose](https://docs.docker.com/compose/install/)

## Getting Started

Follow these steps to get your local development environment up and running.

### 1. Clone the Repository

```bash
git clone <repository_url>
cd <repository_directory>
```

### 2. Set Up Environment Variables

The project uses a `.env` file to manage environment variables. An example file is provided.

```bash
# Copy the example file to create your own local configuration
cp .env.example .env
```

Now, open the `.env` file and review the variables. For local development, the defaults are usually sufficient, but you should **generate a new Fernet key**.

### 3. Generate an Encryption Key

The `DMIGRATE_FERNET_KEY` is used to encrypt database credentials. Generate a new, unique key for your environment:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output and replace the value of `DMIGRATE_FERNET_KEY` in your `.env` file.

### 4. Build and Run the Application

Use Docker Compose to build the images and start the services.

```bash
docker-compose up --build
```

This will start the Django application, the PostgreSQL database, Redis, and a Celery worker. The application will be available at `http://localhost:8000`.

### 5. Apply Database Migrations

In a separate terminal, run the initial database migrations to set up the application's database schema.

```bash
docker-compose exec app python manage.py migrate
```

### 6. Create a Superuser

To access the Django admin interface and use the application, you need to create a superuser account.

```bash
docker-compose exec app python manage.py createsuperuser
```

Follow the prompts to create your admin user. You can now log in to the Django admin at `http://localhost:8000/admin/` and the main UI at `http://localhost:8000/ui/`.

---
## Environment Variables

The following table explains the environment variables used in the `.env` file.

| Variable              | Description                                                                                             | Default Value (in `.env.example`)                  |
|-----------------------|---------------------------------------------------------------------------------------------------------|----------------------------------------------------|
| `DJANGO_SECRET_KEY`   | A secret key for a particular Django installation. This is used to provide cryptographic signing.       | `django-insecure-default-key...`                   |
| `DJANGO_DEBUG`        | Toggles Django's debug mode. Should be `False` in production.                                           | `True`                                             |
| `DB_NAME`             | The name of the PostgreSQL database for the application itself.                                         | `app_db`                                           |
| `DB_USER`             | The username for connecting to the application database.                                                | `app_user`                                         |
| `DB_PASSWORD`         | The password for the application database user.                                                         | `app_password`                                     |
| `DB_HOST`             | The hostname of the database server. Within Docker Compose, this is the service name.                   | `db`                                               |
| `DB_PORT`             | The port on which the database server is listening.                                                     | `5432`                                             |
| `REDIS_HOST`          | The hostname of the Redis server. Within Docker Compose, this is the service name.                      | `redis`                                            |
| `REDIS_PORT`          | The port on which the Redis server is listening.                                                        | `6379`                                             |
| `DMIGRATE_FERNET_KEY` | The secret key used to encrypt and decrypt connection credentials. **Must be kept secure.**             | A sample key. **Generate a new one.**              |

---
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
