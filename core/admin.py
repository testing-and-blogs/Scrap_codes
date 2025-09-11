from django.contrib import admin
from .models import Project, Connection

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin interface for managing Projects."""
    list_display = ('name', 'owner', 'created_at', 'updated_at')
    list_filter = ('owner',)
    search_fields = ('name', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    """Admin interface for managing Connections."""
    list_display = ('name', 'project', 'db_type', 'host', 'port', 'username', 'dbname')
    list_filter = ('project', 'db_type')
    search_fields = ('name', 'host', 'dbname', 'project__name')

    # It's better to use a custom form to handle the password field properly,
    # but for simplicity, we'll allow editing fields directly.
    # We exclude the encrypted field itself to avoid direct manipulation.
    exclude = ('password_encrypted',)

    # To allow setting the password in the admin, you would typically use a custom form
    # with a transient `password` field that then calls the `set_password` method.
    # For now, this will be handled by application logic outside of the admin.
    def get_queryset(self, request):
        # Prefetch related project to optimize queries
        return super().get_queryset(request).select_related('project')
