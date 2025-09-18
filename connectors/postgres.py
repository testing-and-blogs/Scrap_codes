from sqlalchemy import create_engine, text, Engine, inspect
from .base import BaseConnector


class PostgresConnector(BaseConnector):
    """Connector for PostgreSQL databases."""

    def get_engine(self) -> Engine:
        """Constructs a PostgreSQL SQLAlchemy engine."""
        db_uri = (
            f"postgresql+psycopg2://{self.connection_details['username']}:{self.connection_details['password']}"
            f"@{self.connection_details['host']}:{self.connection_details['port']}/{self.connection_details['dbname']}"
        )
        return create_engine(db_uri)

    def test_connection(self) -> tuple[bool, str]:
        """
        Tests the connection to the PostgreSQL database by executing a simple query.
        """
        try:
            engine = self.get_engine()
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True, "Connection to PostgreSQL successful."
        except Exception as e:
            # Provide a more user-friendly error message
            return False, f"PostgreSQL connection failed: {e}"

    def discover_schema(self) -> dict:
        """
        Discovers the schema of the PostgreSQL database using SQLAlchemy's reflection.
        """
        engine = self.get_engine()
        inspector = inspect(engine)
        schema_data = {'tables': []}

        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            pk_constraint = inspector.get_pk_constraint(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)

            table_info = {
                'name': table_name,
                'columns': [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': col['default'],
                    }
                    for col in columns
                ],
                'pk_constraint': pk_constraint,
                'foreign_keys': foreign_keys,
            }
            schema_data['tables'].append(table_info)

        return schema_data
