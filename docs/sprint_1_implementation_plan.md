# Sprint 1 Implementation Plan: Data Mapping UI

This document outlines the plan for implementing the features required for Sprint 1, which focuses on providing a user interface for mapping source database schemas to target schemas.

## 1. Goals & Acceptance Criteria

### Goals
*   Allow users to create and save a "mapping configuration" that defines how data from a source connection should be transformed and loaded into a target connection.
*   Provide a user interface (an editable grid) for creating and modifying these mappings.
*   Enable the generation of Data Definition Language (DDL) to create the target schema based on the mapping.

### Acceptance Criteria
*   A user can create and save a `MappingConfig` by mapping at least one table and a few columns.
*   The mapping must support renaming tables and columns.
*   The mapping must support ignoring certain tables or columns from the migration.
*   The system can generate a `CREATE TABLE` DDL statement for a mapped table.
*   The UI must provide a "Preview DDL" feature.
*   The system must be able to save and load a user's mapping configuration.

## 2. Data Models

To support mapping configurations, the following models will be created in the `mapping` app.

```python
# mapping/models.py

from django.db import models
from core.models import Project

class MappingConfig(models.Model):
    """
    A named configuration that groups together a set of table and column mappings
    for a specific project.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='mapping_configs')
    name = models.CharField(max_length=255)
    source_connection = models.ForeignKey('core.Connection', on_delete=models.CASCADE, related_name='source_mappings')
    target_connection = models.ForeignKey('core.Connection', on_delete=models.CASCADE, related_name='target_mappings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class TableMapping(models.Model):
    """
    Defines the mapping for a single table from the source to the target.
    """
    mapping_config = models.ForeignKey(MappingConfig, on_delete=models.CASCADE, related_name='table_mappings')
    source_table_name = models.CharField(max_length=255)
    target_table_name = models.CharField(max_length=255)
    include_in_migration = models.BooleanField(default=True)

class ColumnMapping(models.Model):
    """
    Defines the mapping for a single column within a table mapping.
    """
    table_mapping = models.ForeignKey(TableMapping, on_delete=models.CASCADE, related_name='column_mappings')
    source_column_name = models.CharField(max_length=255)
    target_column_name = models.CharField(max_length=255)
    target_data_type = models.CharField(max_length=100) # e.g., 'VARCHAR(255)', 'INTEGER'
    transform_expression = models.TextField(blank=True, null=True) # For simple SQL transformations
    is_ignored = models.BooleanField(default=False)
```

## 3. API Endpoints

The following API endpoints will be created in the `ui` app to support the frontend.

### `POST /ui/mappings/save/`
*   **Description**: Saves a new or existing mapping configuration.
*   **Request Body**: A JSON object representing the entire mapping configuration, including table and column mappings.
    ```json
    {
      "name": "My Customer Mapping",
      "project_id": 1,
      "source_connection_id": 1,
      "target_connection_id": 2,
      "tables": [
        {
          "source_table_name": "public.customers",
          "target_table_name": "customers_target",
          "include_in_migration": true,
          "columns": [
            {
              "source_column_name": "id",
              "target_column_name": "customer_id",
              "target_data_type": "INTEGER",
              "is_ignored": false
            },
            // ... other columns
          ]
        }
        // ... other tables
      ]
    }
    ```
*   **Response**: A JSON object confirming success or failure.

### `GET /ui/mappings/<int:mapping_id>/load/`
*   **Description**: Loads an existing mapping configuration to populate the UI.
*   **Response**: A JSON object with the same structure as the save request body.

### `POST /ui/mappings/<int:mapping_id>/preview-ddl/`
*   **Description**: Generates and returns the DDL for the target schema based on the saved mapping.
*   **Response**:
    ```json
    {
      "success": true,
      "ddl": "CREATE TABLE customers_target (customer_id INTEGER, ...);"
    }
    ```

## 4. UI Components

The UI will be built by extending the existing `project_detail.html` template.

*   **Mapping Section**: A new section will be added to the project detail page to manage mapping configurations. It will include a dropdown to select an existing mapping or create a new one.
*   **Mapping Grid**: A new partial template will be created for the mapping grid. This will be a large HTML table where each row represents a source column. The columns of the grid will be:
    *   `Source Table`
    *   `Source Column`
    *   `Source Type`
    *   `Target Table` (editable)
    *   `Target Column` (editable)
    *   `Target Type` (editable/dropdown)
    *   `Actions` (e.g., Ignore checkbox)
*   **JavaScript**: A new JavaScript file or inline script will be written to handle the client-side logic for the mapping grid, including:
    *   Populating the grid from a schema snapshot.
    *   Handling user edits to the grid.
    *   Collecting the grid data into a JSON object.
    *   Calling the `save`, `load`, and `preview-ddl` API endpoints.
    *   Displaying the DDL preview in a modal or text area.

## 5. Testing Strategy

*   **Model Tests**: Unit tests will be written for the `MappingConfig`, `TableMapping`, and `ColumnMapping` models to ensure their fields and relationships are correct.
*   **API Tests**: Integration tests will be written for the `save`, `load`, and `preview-ddl` API endpoints using Django's test client. These tests will mock any backend services (like the DDL generator) to isolate the view logic.
*   **DDL Generation Tests**: Unit tests will be written for the DDL generation service. These tests will provide various mapping configurations as input and assert that the generated DDL string is correct for different database dialects (e.g., PostgreSQL, MySQL).
