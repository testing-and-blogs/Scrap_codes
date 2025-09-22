from abc import ABC, abstractmethod
from sqlalchemy.engine import Engine

class BaseConnector(ABC):
    """
    Abstract Base Class for database connectors.
    It defines a common interface for all connectors to adhere to,
    ensuring that operations like testing connections and discovering schemas
    can be handled polymorphically.
    """

    def __init__(self, connection_details: dict):
        """
        Initializes the connector with the necessary connection details.

        Args:
            connection_details: A dictionary containing keys like 'host', 'port',
                                'username', 'password', and 'dbname'.
        """
        self.connection_details = connection_details

    @abstractmethod
    def get_engine(self) -> Engine:
        """
        Creates and returns a SQLAlchemy engine instance for the specific database.
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """
        Tests the connection to the database.

        Returns:
            A tuple containing a boolean indicating success and a message.
        """
        pass

    @abstractmethod
    def discover_schema(self) -> dict:
        """
        Discovers the schema of the database.

        Returns:
            A dictionary representing the database schema, including tables,
            columns, types, constraints, etc.
        """
        pass

    @abstractmethod
    def get_row_count(self, table_name: str) -> int:
        """
        Gets the total number of rows in a given table.

        Args:
            table_name: The name of the table.

        Returns:
            The total row count as an integer.
        """
        pass

    @abstractmethod
    def upsert(self, table_name: str, data: list[dict], pk_column: str):
        """
        Inserts new rows or updates existing rows in the target database.

        Args:
            table_name: The name of the target table.
            data: A list of dictionaries, where each dictionary represents a row.
            pk_column: The name of the primary key column to use for conflict resolution.
        """
        pass
