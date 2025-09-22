from django.contrib import admin
from .models import ConnectorPlugin

@admin.register(ConnectorPlugin)
class ConnectorPluginAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Connector Plugins.
    """
    list_display = ('name', 'plugin_key', 'is_enabled')
    list_editable = ('is_enabled',)
    search_fields = ('name', 'plugin_key')

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the built-in plugins from the admin
        return False

    def has_add_permission(self, request):
        # Prevent adding new plugins from the admin, as they need code support
        return False
