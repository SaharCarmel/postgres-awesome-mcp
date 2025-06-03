# PostgreSQL MCP Server

A Model Context Protocol server that provides tools for querying PostgreSQL databases. Supports multiple named database connections.

## Features

- **execute_query**: Execute SQL queries with optional database selection
- **list_tables**: List all tables in a schema from any configured database
- **describe_table**: Get detailed table structure information from any database
- **list_databases**: List all configured database connections
- **sql_query_helper**: Prompt template for SQL query assistance
- **Multi-database support**: Connect to multiple PostgreSQL servers simultaneously

## Installation

### For Cline Users

If you're using this MCP server with Cline, see the [Cline Installation Guide](CLINE_INSTALLATION.md) for detailed setup instructions.

### General Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/SaharCarmel/postgres-awesome-mcp.git
   cd postgres-awesome-mcp
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

## Configuration

### Single Database (Backward Compatible)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your PostgreSQL connection details:
   ```
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DATABASE=your_database
   POSTGRES_USER=your_username
   POSTGRES_PASSWORD=your_password
   ```

### Multiple Databases

1. Copy the example configuration file:
   ```bash
   cp databases.json.example databases.json
   ```

2. Edit `databases.json` with your multiple database configurations:
   ```json
   {
     "databases": {
       "primary": {
         "host": "localhost",
         "port": 5432,
         "database": "main_db",
         "user": "postgres",
         "password": "password1"
       },
       "analytics": {
         "host": "analytics-server.com",
         "port": 5432,
         "database": "analytics_db",
         "user": "analyst",
         "password": "password2"
       }
     },
     "default_database": "primary"
   }
   ```

3. Optionally set the config file path:
   ```bash
   export POSTGRES_CONFIG_FILE=databases.json
   ```

## Usage

### Running the Server

```bash
# Using stdio transport (default)
uv run server.py

# Or using the MCP CLI
uv run mcp run server.py
```

### Testing with MCP Inspector

```bash
uv run mcp dev server.py
```

### Installing in Claude Desktop

```bash
uv run mcp install server.py --name "PostgreSQL Server"
```

## Available Tools

### execute_query
Execute SQL queries against any configured PostgreSQL database.

**Parameters:**
- `query` (string): The SQL query to execute
- `database_id` (string, optional): Database identifier. Uses default if not specified.

**Examples:**
```python
# Use default database
result = await session.call_tool("execute_query", {
    "query": "SELECT * FROM users WHERE active = true LIMIT 10"
})

# Use specific database
result = await session.call_tool("execute_query", {
    "query": "SELECT * FROM logs WHERE date > '2025-01-01'",
    "database_id": "analytics"
})
```

### list_tables
List all tables in a specified schema from any database.

**Parameters:**
- `schema` (string, optional): Schema name (default: "public")
- `database_id` (string, optional): Database identifier. Uses default if not specified.

**Examples:**
```python
# Default database
tables = await session.call_tool("list_tables", {"schema": "public"})

# Specific database
tables = await session.call_tool("list_tables", {
    "schema": "public", 
    "database_id": "analytics"
})
```

### describe_table
Get detailed information about a specific table from any database.

**Parameters:**
- `table_name` (string): Name of the table to describe
- `schema` (string, optional): Schema name (default: "public")
- `database_id` (string, optional): Database identifier. Uses default if not specified.

**Examples:**
```python
# Default database
info = await session.call_tool("describe_table", {
    "table_name": "users",
    "schema": "public"
})

# Specific database
info = await session.call_tool("describe_table", {
    "table_name": "events",
    "schema": "public",
    "database_id": "analytics"
})
```

### list_databases
List all available database connections configured in the MCP server.

**Parameters:**
None

**Example:**
```python
databases = await session.call_tool("list_databases", {})
print("Available databases:", databases["databases"])
```

## Available Resources

> **Note:** In multi-database mode, resources are limited to providing informational messages. Use the corresponding tools (`list_tables`, `describe_table`) instead for actual database operations.

### schema://tables
Provides information about table resource limitations.

### schema://table/{table_name}
Provides information about table resource limitations.

## Available Prompts

### sql_query_helper
Generate helpful prompts for writing SQL queries.

**Parameters:**
- `table_name` (string): The table to query
- `operation` (string, optional): SQL operation type (default: "SELECT")

## Example Client Code

```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

async def main():
    async with stdio_client(
        StdioServerParameters(command="uv", args=["run", "server.py"])
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

            # Execute a query
            result = await session.call_tool("execute_query", {
                "query": "SELECT version()"
            })
            print("Query result:", result)

            # List tables
            tables = await session.call_tool("list_tables", {})
            print("Tables:", tables)

            # Get schema overview
            schema = await session.read_resource("schema://tables")
            print("Schema:", schema)

if __name__ == "__main__":
    asyncio.run(main())
```

## Security Notes

- The server executes SQL queries directly against your database
- Ensure proper database permissions are set for the connecting user
- Consider using read-only database users for SELECT-only access
- Always validate and sanitize queries in production environments

## Troubleshooting

### Connection Issues
- Verify your `.env` file has correct database credentials
- Ensure PostgreSQL is running and accessible
- Check firewall settings if connecting to remote database

### Permission Issues
- Ensure the database user has appropriate permissions
- For schema introspection, the user needs access to `information_schema`

### Import Errors
- Make sure you're running commands with `uv run` to use the virtual environment
- Verify all dependencies are installed with `uv sync`
