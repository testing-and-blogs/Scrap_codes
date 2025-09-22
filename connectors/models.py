from django.db import models

class ConnectorPlugin(models.Model):
    """
    A model to manage the availability of database connector plugins.
    Administrators can enable or disable connectors through the Django admin.
    """
    name = models.CharField(max_length=100, unique=True, help_text="A user-friendly name for the connector, e.g., 'PostgreSQL'.")
    # The plugin_key must match the key used in the Connection model's DbType choices
    plugin_key = models.CharField(max_length=50, unique=True, primary_key=True, help_text="The internal key for the plugin, e.g., 'postgres'.")
    is_enabled = models.BooleanField(default=True, help_text="Enable or disable this connector across the application.")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Connector Plugin"
        verbose_name_plural = "Connector Plugins"
