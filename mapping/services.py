from .models import MappingConfig

def generate_ddl(mapping_config: MappingConfig) -> str:
    """
    Generates the Data Definition Language (DDL) for the target schema based on
    a given mapping configuration.

    This service abstracts the logic of converting a mapping into a valid
    SQL `CREATE TABLE` statement, with basic handling for different SQL dialects.

    Args:
        mapping_config: The MappingConfig instance to generate DDL for.

    Returns:
        A string containing the DDL statements.
    """
    ddl_statements = []
    target_db_type = mapping_config.target_connection.db_type

    # Iterate over tables that are marked for inclusion
    for table_mapping in mapping_config.table_mappings.filter(include_in_migration=True):

        columns_sql_parts = []
        # Iterate over columns that are not ignored
        for col_mapping in table_mapping.column_mappings.filter(is_ignored=False):
            # A real-world implementation would need more robust type mapping,
            # handling of constraints (PK, FK, UNIQUE), defaults, etc.
            # This is a simplified version for the MVP.
            columns_sql_parts.append(f"    \"{col_mapping.target_column_name}\" {col_mapping.target_data_type}")

        # If a table has no columns to be migrated, skip it.
        if not columns_sql_parts:
            continue

        columns_sql = ",\n".join(columns_sql_parts)
        table_name = table_mapping.target_table_name

        # Basic SQL dialect handling
        if target_db_type == 'postgres':
            # Using IF NOT EXISTS is safer for re-runnable operations
            statement = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" (\n{columns_sql}\n);"
        elif target_db_type == 'mysql':
            statement = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n{columns_sql}\n) ENGINE=InnoDB;"
        else:
            # Generic fallback (less safe)
            statement = f"CREATE TABLE \"{table_name}\" (\n{columns_sql}\n);"

        ddl_statements.append(statement)

    return "\n\n".join(ddl_statements)
