# PostgreSQL MCP Server

A Model Context Protocol server that provides tools for querying PostgreSQL databases.

## Features

- **execute_query**: Execute SQL queries (SELECT, INSERT, UPDATE, DELETE)
- **list_tables**: List all tables in a schema
- **describe_table**: Get detailed table structure information
- **schema resources**: Access database schema as MCP resources
- **sql_query_helper**: Prompt template for SQL query assistance

## Installation

### For Cline Users

If you're using this MCP server with Cline, see the [Cline Installation Guide](CLINE_INSTALLATION.md) for detailed setup instructions.

### General Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Marble-rnd/pg-mcp.git
   cd pg-mcp
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

## Configuration

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
Execute SQL queries against your PostgreSQL database.

**Parameters:**
- `query` (string): The SQL query to execute

**Example:**
```python
result = await session.call_tool("execute_query", {
    "query": "SELECT * FROM users WHERE active = true LIMIT 10"
})
```

### list_tables
List all tables in a specified schema.

**Parameters:**
- `schema` (string, optional): Schema name (default: "public")

**Example:**
```python
tables = await session.call_tool("list_tables", {"schema": "public"})
```

### describe_table
Get detailed information about a specific table.

**Parameters:**
- `table_name` (string): Name of the table to describe
- `schema` (string, optional): Schema name (default: "public")

**Example:**
```python
info = await session.call_tool("describe_table", {
    "table_name": "users",
    "schema": "public"
})
```

## Available Resources

### schema://tables
Get a comprehensive overview of all tables in the database.

**Example:**
```python
schema = await session.read_resource("schema://tables")
```

### schema://table/{table_name}
Get detailed schema information for a specific table.

**Example:**
```python
table_schema = await session.read_resource("schema://table/users")
```

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
