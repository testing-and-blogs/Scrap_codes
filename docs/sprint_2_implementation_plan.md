# Sprint 2 Implementation Plan: Migration Execution Engine

This document outlines the plan for implementing the features for Sprint 2. The primary goal of this sprint is to build the core engine that can execute a data migration based on a user-defined mapping configuration. The engine will be built on Celery for asynchronous execution and will be designed for robustness and resumability.

## 1. Goals & Acceptance Criteria

### Goals
*   Execute a data migration as a background job.
*   Track the progress and status of each migration job.
*   Ensure migrations are resumable in case of failure.
*   Provide a basic UI for users to start and monitor their migration jobs.

### Acceptance Criteria
*   A user can start a migration job from a saved `MappingConfig`.
*   The system creates a `MigrationJob` record to track the overall task.
*   The job is split into multiple `MigrationChunk`s, each representing a portion of a table's data.
*   Each chunk is processed as an individual background task.
*   The status of the job and each chunk is updated in real-time.
*   If a chunk fails, the error is logged, and the job is paused.
*   (Stretch Goal) A user can resume a failed job, and it will continue from the last successful chunk.
*   A user can view the details and progress of a job on a dedicated page.

## 2. Data Models

The following models will be created in the `jobs` app to manage the state of migrations.

```python
# jobs/models.py

from django.db import models

class MigrationJob(models.Model):
    """
    Represents a single, end-to-end migration job.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        PAUSED = 'PAUSED', 'Paused'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    mapping_config = models.ForeignKey('mapping.MappingConfig', on_delete=models.CASCADE, related_name='migration_jobs')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Job for {self.mapping_config.name} ({self.status})"

class MigrationChunk(models.Model):
    """
    Represents a single chunk of work in a migration job, typically a range of
    rows from a single source table.
    """
    job = models.ForeignKey(MigrationJob, on_delete=models.CASCADE, related_name='chunks')
    source_table_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=MigrationJob.Status.choices, default=MigrationJob.Status.PENDING)

    # Checkpointing / Cursor
    # For simplicity, we'll start with offset-based chunking.
    # A more robust solution would use keyset pagination (e.g., last processed PK).
    offset = models.PositiveIntegerField()
    limit = models.PositiveIntegerField()

    processed_rows = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
```

## 3. Celery Task Architecture

The migration process will be managed by two main Celery tasks in a new `jobs/tasks.py` file.

### `start_migration_job(job_id: int)`
*   **Trigger**: Called from a view when a user clicks "Start Migration".
*   **Responsibilities**:
    1.  Sets the `MigrationJob` status to `RUNNING`.
    2.  Fetches the associated `MappingConfig` and its table mappings.
    3.  For each table to be migrated, it calculates the number of chunks needed (e.g., based on `COUNT(*)` and a configured chunk size).
    4.  Creates `MigrationChunk` records in the database for each chunk of each table, with a `PENDING` status.
    5.  Dispatches `process_migration_chunk` tasks for each chunk to the Celery queue.

### `process_migration_chunk(chunk_id: int)`
*   **Trigger**: Dispatched by `start_migration_job`.
*   **Responsibilities**:
    1.  Sets the `MigrationChunk` status to `RUNNING`.
    2.  Connects to the source and target databases.
    3.  **Extract**: Fetches data from the source table using the chunk's `offset` and `limit`.
    4.  **Transform**: Iterates through the extracted rows and applies the transformations defined in the `ColumnMapping` (e.g., renaming columns).
    5.  **Load**: Inserts the transformed data into the target table in a transaction.
    6.  **Checkpoint**: On success, sets the chunk status to `SUCCESS`. On failure, sets the status to `FAILED`, logs the error message, and pauses the parent `MigrationJob`.

## 4. UI Components & Views

### Views (`ui/views.py`)
*   **`start_migration_view(request, mapping_id)`**:
    *   Creates a new `MigrationJob` instance.
    *   Calls `start_migration_job.delay(job.id)`.
    *   Redirects the user to the new job detail page.
*   **`job_detail_view(request, job_id)`**:
    *   Renders a page showing the `MigrationJob`'s overall status.
    *   Fetches and displays a list of all `MigrationChunk`s associated with the job, showing their individual statuses.
    *   (Future) This page will include controls for pause/resume/retry.

### Templates
*   **`project_detail.html`**:
    *   A "Start Migration" button will be added next to each saved `MappingConfig`.
    *   A list of past and current migration jobs for the project will be displayed.
*   **`jobs/job_detail.html`**:
    *   A new template to display the job and chunk details.
    *   Will include auto-refreshing logic (e.g., using HTMX or simple JavaScript polling) to show progress in near real-time.

## 5. Testing Strategy

*   **Model Tests**: Unit tests for `MigrationJob` and `MigrationChunk`.
*   **Celery Task Tests**: Integration tests for the `start_migration_job` and `process_migration_chunk` tasks. These tests will need to:
    *   Use `celery.contrib.testing` to run tasks synchronously.
    *   Mock the database connectors to avoid real database connections.
    *   Assert that the tasks correctly create chunks, process data, and update statuses.
*   **View Tests**: Tests for the `start_migration_view` and `job_detail_view` to ensure they are secure and render the correct data.
