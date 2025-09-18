from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.models import Connection
from connectors.factory import get_connector

@login_required
@require_POST
def test_connection_view(request, connection_id: int):
    """
    An API endpoint to test a database connection.
    It expects a POST request.

    This view ensures that the user making the request is the owner of the
    project associated with the connection, preventing unauthorized access.

    Args:
        request: The HttpRequest object.
        connection_id: The primary key of the Connection to test.

    Returns:
        A JsonResponse with 'success' (bool) and 'message' (str) keys.
    """
    # Ensure the user can only access connections they own.
    connection = get_object_or_404(Connection, pk=connection_id, project__owner=request.user)

    try:
        connector = get_connector(connection)
        success, message = connector.test_connection()
        status_code = 200 if success else 400
        return JsonResponse({'success': success, 'message': message}, status=status_code)
    except Exception as e:
        # This catches errors from get_connector (e.g., unsupported db_type)
        # or any other unexpected errors during the process.
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

from django.shortcuts import render
from core.models import Project
from mapping.models import SchemaSnapshot

@login_required
def dashboard_view(request):
    """
    Displays a list of the user's projects.
    """
    projects = Project.objects.filter(owner=request.user)
    context = {
        'projects': projects,
    }
    return render(request, 'ui/dashboard.html', context)

@login_required
def project_detail_view(request, project_id: int):
    """
    Displays the details of a single project, including its connections
    and the latest schema snapshot for each connection.
    """
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    # Using prefetch_related to optimize queries
    connections = project.connections.all().prefetch_related('schema_snapshots')
    mappings = project.mapping_configs.all()

    context = {
        'project': project,
        'connections': connections,
        'mappings': mappings,
    }
    return render(request, 'ui/project_detail.html', context)

@login_required
@require_POST
def discover_schema_view(request, connection_id: int):
    """
    An API endpoint to trigger schema discovery for a connection.
    Creates a new SchemaSnapshot instance with the discovered schema.
    """
    connection = get_object_or_404(Connection, pk=connection_id, project__owner=request.user)
    try:
        connector = get_connector(connection)
        schema_data = connector.discover_schema()

        # Create a new snapshot
        snapshot = SchemaSnapshot.objects.create(
            connection=connection,
            schema=schema_data
        )

        return JsonResponse({
            'success': True,
            'snapshot_id': snapshot.id,
            'message': f'Schema discovered successfully for {connection.name}.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

import json
from django.db import transaction
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
from mapping.models import MappingConfig, TableMapping, ColumnMapping
from mapping.services import generate_ddl
from jobs.models import MigrationJob
from jobs.tasks import start_migration_job

@login_required
@require_http_methods(["POST"])
@transaction.atomic
def save_mapping_config_view(request):
    """
    Saves a new or updates an existing mapping configuration from a JSON payload.
    """
    try:
        data = json.loads(request.body)
        project = get_object_or_404(Project, pk=data['project_id'], owner=request.user)

        # Create or update the MappingConfig
        mapping_config, created = MappingConfig.objects.update_or_create(
            project=project,
            name=data['name'],
            defaults={
                'source_connection_id': data['source_connection_id'],
                'target_connection_id': data['target_connection_id'],
            }
        )

        # Clear old mappings to replace them
        mapping_config.table_mappings.all().delete()

        # Create new table and column mappings
        for table_data in data.get('tables', []):
            table_mapping = TableMapping.objects.create(
                mapping_config=mapping_config,
                source_table_name=table_data['source_table_name'],
                target_table_name=table_data['target_table_name'],
                include_in_migration=table_data['include_in_migration']
            )

            for column_data in table_data.get('columns', []):
                ColumnMapping.objects.create(
                    table_mapping=table_mapping,
                    source_column_name=column_data['source_column_name'],
                    target_column_name=column_data['target_column_name'],
                    target_data_type=column_data['target_data_type'],
                    is_ignored=column_data.get('is_ignored', False)
                )

        return JsonResponse({'success': True, 'mapping_id': mapping_config.id, 'message': 'Mapping saved successfully.'})

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def load_mapping_config_view(request, mapping_id: int):
    """
    Loads and returns a mapping configuration as a JSON object.
    """
    mapping_config = get_object_or_404(MappingConfig, pk=mapping_id, project__owner=request.user)

    response_data = {
        'id': mapping_config.id,
        'name': mapping_config.name,
        'project_id': mapping_config.project.id,
        'source_connection_id': mapping_config.source_connection.id,
        'target_connection_id': mapping_config.target_connection.id,
        'tables': []
    }

    table_mappings = mapping_config.table_mappings.prefetch_related('column_mappings').all()

    for table_mapping in table_mappings:
        table_data = {
            'source_table_name': table_mapping.source_table_name,
            'target_table_name': table_mapping.target_table_name,
            'include_in_migration': table_mapping.include_in_migration,
            'columns': []
        }
        for column_mapping in table_mapping.column_mappings.all():
            table_data['columns'].append({
                'source_column_name': column_mapping.source_column_name,
                'target_column_name': column_mapping.target_column_name,
                'target_data_type': column_mapping.target_data_type,
                'is_ignored': column_mapping.is_ignored
            })
        response_data['tables'].append(table_data)

    return JsonResponse(response_data)


@login_required
@require_http_methods(["POST"]) # Using POST as it may trigger computation
def preview_ddl_view(request, mapping_id: int):
    """
    Generates and returns a DDL preview for a given mapping configuration.
    """
    mapping_config = get_object_or_404(MappingConfig, pk=mapping_id, project__owner=request.user)

    try:
        ddl_string = generate_ddl(mapping_config)
        return JsonResponse({'success': True, 'ddl': ddl_string})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def start_migration_view(request, mapping_id: int):
    """
    Creates a MigrationJob and kicks off the Celery task to run it.
    """
    mapping_config = get_object_or_404(MappingConfig, pk=mapping_id, project__owner=request.user)

    # Create the job record
    job = MigrationJob.objects.create(
        mapping_config=mapping_config,
        status=MigrationJob.Status.PENDING
    )

    # Dispatch the background task
    start_migration_job.delay(job.id)

    # Redirect to the new job's detail page
    return redirect('ui:job_detail', job_id=job.id)


@login_required
@require_http_methods(["GET"])
def job_detail_view(request, job_id: int):
    """
    Displays the status and details of a single migration job.
    """
    job = get_object_or_404(
        MigrationJob.objects.prefetch_related('chunks'),
        pk=job_id,
        mapping_config__project__owner=request.user
    )

    context = {
        'job': job
    }

    return render(request, 'ui/job_detail.html', context)
