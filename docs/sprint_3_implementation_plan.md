# Sprint 3 Implementation Plan: Data Sync & Admin Panels

This document outlines the plan for implementing the features for Sprint 3. This sprint is divided into two main parts:
1.  **Data Synchronization**: Adding the ability for users to schedule recurring synchronization jobs to keep their data up-to-date after an initial migration.
2.  **Admin Panels**: Enhancing the Django Admin to provide powerful management and monitoring capabilities for system administrators.

---

## Part A: Data Synchronization

### 1. Goals & Acceptance Criteria
*   **Goal**: Allow users to keep their target database in sync with the source after the initial migration is complete.
*   **Acceptance Criteria**:
    *   A user can enable a "sync schedule" for a `MappingConfig`.
    *   The user can choose a frequency (e.g., Hourly, Daily) and a sync key (e.g., `updated_at` timestamp or an auto-incrementing `id`).
    *   The system automatically runs sync jobs at the specified frequency using Celery Beat.
    *   Sync jobs correctly identify and transfer only new or updated records from the source.
    *   The sync logic supports an "upsert" operation (insert new records, update existing ones).
    *   The UI displays the status and history of sync jobs.

### 2. Data Models & Migrations
A new model will be added to the `jobs` app to manage sync schedules.

```python
# jobs/models.py

class SyncSchedule(models.Model):
    """
    Defines a recurring synchronization schedule for a mapping configuration.
    """
    class Frequency(models.TextChoices):
        HOURLY = 'HOURLY', 'Hourly'
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'

    mapping_config = models.OneToOneField('mapping.MappingConfig', on_delete=models.CASCADE, related_name='sync_schedule')
    is_active = models.BooleanField(default=False)
    frequency = models.CharField(max_length=20, choices=Frequency.choices)

    # Sync Key Configuration
    sync_key_column = models.CharField(max_length=255, help_text="The column used to detect new/updated rows (e.g., 'id' or 'updated_at').")
    last_sync_value = models.CharField(max_length=255, null=True, blank=True, help_text="The last value of the sync key that was processed.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 3. Celery Beat & Sync Tasks
*   **Celery Beat Configuration**:
    *   A new schedule will be added to `settings.py` for Celery Beat. It will trigger a scheduler task every minute.
    *   `CELERY_BEAT_SCHEDULE = { 'schedule-syncs': { 'task': 'jobs.tasks.schedule_due_syncs', 'schedule': crontab(minute='*') } }`
*   **`schedule_due_syncs()` Task**:
    *   This periodic task will query all active `SyncSchedule`s.
    *   For each schedule, it will check if it's time to run based on its `frequency` and `updated_at` time.
    *   If a sync is due, it will dispatch the `run_sync_job` task.
*   **`run_sync_job(schedule_id)` Task**:
    *   This task will perform the actual data sync.
    *   It will be similar to `process_migration_chunk`, but instead of chunking the whole table, it will query the source using the `sync_key_column` and `last_sync_value`.
    *   Example query: `SELECT * FROM source_table WHERE sync_key > :last_value ORDER BY sync_key`.
    *   It will perform an "upsert" into the target database. This will require adding an `upsert` method to the `BaseConnector` interface.
    *   Upon completion, it will update the `last_sync_value` on the `SyncSchedule` object.

---

## Part B: Admin Panels

### 1. Goals & Acceptance Criteria
*   **Goal**: Provide administrators with the tools to manage and monitor the entire data migration service.
*   **Acceptance Criteria**:
    *   An admin can view a list of all `MigrationJob`s in the system.
    *   An admin can trigger an action to "force-stop" a running job (set its status to `FAILED`).
    *   An admin can enable or disable database connector plugins.
    *   The Django Admin provides a usable interface for managing all core models.

### 2. Django Admin Enhancements
*   **`jobs/admin.py`**:
    *   Create a `MigrationJobAdmin` class.
    *   Add `status` and `mapping_config` to `list_display` and `list_filter`.
    *   Implement a custom admin action `force_stop_jobs`. This action will take selected jobs and update their status to `FAILED`.
*   **`core/admin.py` & `mapping/admin.py`**:
    *   Review existing `ModelAdmin` classes and enhance them with more useful filters, search fields, and display fields to improve usability.

### 3. Plugin Management
*   **New Model**: Create a new model `connectors.ConnectorPlugin` to manage the availability of connectors.
    ```python
    # connectors/models.py
    class ConnectorPlugin(models.Model):
        name = models.CharField(max_length=100, unique=True)
        # e.g., 'postgres', 'mysql'
        plugin_key = models.CharField(max_length=50, unique=True, primary_key=True)
        is_enabled = models.BooleanField(default=True)
    ```
*   **Admin Interface**: Create a `ModelAdmin` for `ConnectorPlugin` where an admin can simply check/uncheck the `is_enabled` box.
*   **Factory Update**: The `get_connector` factory in `connectors/factory.py` will be updated to first check if the requested plugin is enabled in the database before returning the connector instance.

## 4. Testing Strategy
*   **Sync Tests**:
    *   Unit tests for the `SyncSchedule` model.
    *   Tests for the `schedule_due_syncs` Celery task to ensure it correctly queues jobs.
    *   Integration tests for the `run_sync_job` task, mocking the database connectors and verifying the incremental query logic and upsert calls.
*   **Admin Tests**:
    *   Tests for the `force_stop_jobs` admin action.
    *   Tests to ensure that disabling a connector via the admin prevents it from being used.
