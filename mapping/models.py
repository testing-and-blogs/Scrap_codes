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
