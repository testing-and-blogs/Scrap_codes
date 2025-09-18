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
