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
