from django.urls import path
from . import views

app_name = 'ui'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Project specific
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),

    # API-like endpoints
    path('connections/<int:connection_id>/test/', views.test_connection_view, name='test_connection'),
    path('connections/<int:connection_id>/discover-schema/', views.discover_schema_view, name='discover_schema'),
]
