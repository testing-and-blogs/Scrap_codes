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
