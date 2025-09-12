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
