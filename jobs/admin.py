from django.contrib import admin, messages
from .models import MigrationJob, MigrationChunk, SyncSchedule

@admin.action(description='Force stop selected jobs')
def force_stop_jobs(modeladmin, request, queryset):
    """
    Admin action to mark running or pending jobs as FAILED.
    """
    updated_count = queryset.update(status=MigrationJob.Status.FAILED)
    modeladmin.message_user(request, f'{updated_count} jobs were marked as failed.', messages.SUCCESS)

class MigrationChunkInline(admin.TabularInline):
    """
    Inline admin view for MigrationChunks, shown within the MigrationJob detail view.
    """
    model = MigrationChunk
    extra = 0
    readonly_fields = ('status', 'offset', 'limit', 'processed_rows', 'error_message', 'created_at', 'finished_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(MigrationJob)
class MigrationJobAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Migration Jobs.
    """
    list_display = ('id', 'mapping_config', 'status', 'created_at', 'finished_at')
    list_filter = ('status',)
    search_fields = ('mapping_config__name', 'id')
    readonly_fields = ('created_at', 'finished_at', 'error_message')
    inlines = [MigrationChunkInline]
    actions = [force_stop_jobs]

@admin.register(SyncSchedule)
class SyncScheduleAdmin(admin.ModelAdmin):
    """
    Admin interface for managing Sync Schedules.
    """
    list_display = ('mapping_config', 'is_active', 'frequency', 'sync_key_column', 'updated_at')
    list_editable = ('is_active', 'frequency')
    search_fields = ('mapping_config__name',)
