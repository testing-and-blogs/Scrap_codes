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
    # Using prefetch_related to optimize the query for schema_snapshots
    connections = project.connections.all().prefetch_related('schema_snapshots')

    context = {
        'project': project,
        'connections': connections,
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
