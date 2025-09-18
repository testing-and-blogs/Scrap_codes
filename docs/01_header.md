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
