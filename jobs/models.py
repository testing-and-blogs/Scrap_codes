from django.db import models

class MigrationJob(models.Model):
    """
    Represents a single, end-to-end migration job, tracking its overall status
    and linking it to the mapping configuration it uses.
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
        return f"Job #{self.id} for {self.mapping_config.name} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class MigrationChunk(models.Model):
    """
    Represents a single chunk of work in a migration job, typically a range of
    rows from a single source table. This model is key to enabling resumability.
    """
    job = models.ForeignKey(MigrationJob, on_delete=models.CASCADE, related_name='chunks')
    table_mapping = models.ForeignKey('mapping.TableMapping', on_delete=models.CASCADE, related_name='chunks')
    status = models.CharField(max_length=20, choices=MigrationJob.Status.choices, default=MigrationJob.Status.PENDING)

    # For simplicity, we'll start with offset-based chunking.
    # A more robust solution would use keyset pagination (e.g., last processed PK).
    offset = models.PositiveIntegerField()
    limit = models.PositiveIntegerField()

    processed_rows = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Chunk #{self.id} for table {self.table_mapping.source_table_name} (Job #{self.job.id})"

    class Meta:
        ordering = ['created_at']


class SyncSchedule(models.Model):
    """
    Defines a recurring synchronization schedule for a mapping configuration.
    """
    class Frequency(models.TextChoices):
        HOURLY = 'HOURLY', 'Hourly'
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'

    mapping_config = models.OneToOneField('mapping.MappingConfig', on_delete=models.CASCADE, related_name='sync_schedule')
    is_active = models.BooleanField(default=True)
    frequency = models.CharField(max_length=20, choices=Frequency.choices)

    sync_key_column = models.CharField(max_length=255, help_text="The column used to detect new/updated rows (e.g., 'id' or 'updated_at').")
    last_sync_value = models.CharField(max_length=255, null=True, blank=True, help_text="The last value of the sync key that was processed.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sync schedule for {self.mapping_config.name} ({self.frequency})"

    class Meta:
        ordering = ['-updated_at']


class SyncJob(models.Model):
    """
    Represents a single run of a synchronization schedule.
    This allows for detailed tracking of each sync execution.
    """
    sync_schedule = models.ForeignKey(SyncSchedule, on_delete=models.CASCADE, related_name='sync_jobs')
    status = models.CharField(max_length=20, choices=MigrationJob.Status.choices, default=MigrationJob.Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Sync Job #{self.id} for {self.sync_schedule.mapping_config.name} ({self.status})"

    class Meta:
        ordering = ['-created_at']
