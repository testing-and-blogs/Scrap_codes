from django.urls import path
from . import views

app_name = 'ui'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Project specific
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),

    # API-like endpoints for Connections
    path('connections/<int:connection_id>/test/', views.test_connection_view, name='test_connection'),
    path('connections/<int:connection_id>/discover-schema/', views.discover_schema_view, name='discover_schema'),

    # API-like endpoints for Mappings
    path('mappings/save/', views.save_mapping_config_view, name='save_mapping_config'),
    path('mappings/<int:mapping_id>/load/', views.load_mapping_config_view, name='load_mapping_config'),
    path('mappings/<int:mapping_id>/preview-ddl/', views.preview_ddl_view, name='preview_ddl'),
    path('mappings/<int:mapping_id>/start-migration/', views.start_migration_view, name='start_migration'),
    path('mappings/<int:mapping_id>/save-sync/', views.save_sync_schedule_view, name='save_sync_schedule'),

    # Job monitoring
    path('jobs/<int:job_id>/', views.job_detail_view, name='job_detail'),
]
