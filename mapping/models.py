from django.db import models
from core.models import Connection

class SchemaSnapshot(models.Model):
    """
    Represents a point-in-time snapshot of a database's schema.
    This is stored as a JSON object, allowing for flexibility in the
    structure of the discovered schema data.
    """
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='schema_snapshots')
    schema = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Schema for {self.connection.name} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Schema Snapshot"
        verbose_name_plural = "Schema Snapshots"


class MappingConfig(models.Model):
    """
    A named configuration that groups together a set of table and column mappings
    for a specific project.
    """
    project = models.ForeignKey('core.Project', on_delete=models.CASCADE, related_name='mapping_configs')
    name = models.CharField(max_length=255, unique=True)
    source_connection = models.ForeignKey('core.Connection', on_delete=models.CASCADE, related_name='source_mappings')
    target_connection = models.ForeignKey('core.Connection', on_delete=models.CASCADE, related_name='target_mappings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class TableMapping(models.Model):
    """
    Defines the mapping for a single table from the source to the target.
    """
    mapping_config = models.ForeignKey(MappingConfig, on_delete=models.CASCADE, related_name='table_mappings')
    source_table_name = models.CharField(max_length=255)
    target_table_name = models.CharField(max_length=255)
    include_in_migration = models.BooleanField(default=True)

    class Meta:
        unique_together = ('mapping_config', 'source_table_name')


class ColumnMapping(models.Model):
    """
    Defines the mapping for a single column within a table mapping.
    """
    table_mapping = models.ForeignKey(TableMapping, on_delete=models.CASCADE, related_name='column_mappings')
    source_column_name = models.CharField(max_length=255)
    target_column_name = models.CharField(max_length=255)
    target_data_type = models.CharField(max_length=100)
    transform_expression = models.TextField(blank=True, null=True)
    is_ignored = models.BooleanField(default=False)

    class Meta:
        unique_together = ('table_mapping', 'source_column_name')
