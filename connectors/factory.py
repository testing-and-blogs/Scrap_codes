from core.models import Connection
from .models import ConnectorPlugin
from .base import BaseConnector
from .postgres import PostgresConnector
from .mysql import MySqlConnector

def get_connector(connection: Connection) -> BaseConnector:
    """
    Factory function to get the appropriate connector instance for a given
    Connection object.

    This function abstracts away the logic of selecting the correct connector
    class, making the code that uses connectors cleaner and easier to maintain.

    Args:
        connection: The Connection model instance for which to get a connector.

    Returns:
        An instance of a BaseConnector subclass.

    Raises:
        ValueError: If the connection's db_type is not supported.
    """
    try:
        plugin = ConnectorPlugin.objects.get(plugin_key=connection.db_type)
        if not plugin.is_enabled:
            raise ValueError(f"The '{plugin.name}' connector is currently disabled by an administrator.")
    except ConnectorPlugin.DoesNotExist:
        raise ValueError(f"A connector plugin for the type '{connection.db_type}' is not installed.")

    connection_details = {
        'host': connection.host,
        'port': connection.port,
        'username': connection.username,
        'password': connection.get_password(),
        'dbname': connection.dbname,
    }

    if connection.db_type == Connection.DbType.POSTGRES:
        return PostgresConnector(connection_details)
    elif connection.db_type == Connection.DbType.MYSQL:
        return MySqlConnector(connection_details)
    else:
        # This case should now be caught by the DoesNotExist exception above,
        # but we'll keep it as a fallback.
        raise ValueError(f"Unsupported database type: '{connection.db_type}'")
