# PostgreSQL MCP Server - Cline Installation Guide

This guide explains how to install and configure the PostgreSQL MCP server for use with Cline.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager installed
- PostgreSQL database access
- Cline extension installed in VS Code

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/Marble-rnd/pg-mcp.git
cd pg-mcp
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configure Database Connection

Copy the example environment file and configure your database credentials:

```bash
cp .env.example .env
```

Edit `.env` with your PostgreSQL connection details:

```env
POSTGRES_HOST=your-postgres-host
POSTGRES_PORT=5432
POSTGRES_DATABASE=your-database-name
POSTGRES_USER=your-username
POSTGRES_PASSWORD=your-password
```

### 4. Test the Server

Verify the server works with your database:

```bash
uv run mcp dev server.py
```

This will start the MCP Inspector at http://127.0.0.1:6274 where you can test the tools.

### 5. Add to Cline Configuration

#### Option A: Automatic Installation (Recommended)

Use the MCP CLI to automatically add the server to Cline:

```bash
uv run mcp install server.py --name "PostgreSQL Server"
```

#### Option B: Manual Configuration

1. Open Cline's MCP settings file:
   - **macOS**: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
   - **Windows**: `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
   - **Linux**: `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

2. Add the following configuration to the `mcpServers` object:

```json
{
  "mcpServers": {
    "postgres-mcp": {
      "autoApprove": [
        "execute_query",
        "list_tables",
        "describe_table"
      ],
      "disabled": false,
      "timeout": 60,
      "command": "/path/to/uv",
      "args": [
        "run",
        "--directory",
        "/path/to/pg-mcp",
        "server.py"
      ],
      "env": {
        "POSTGRES_HOST": "your-postgres-host",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DATABASE": "your-database-name",
        "POSTGRES_USER": "your-username",
        "POSTGRES_PASSWORD": "your-password"
      },
      "transportType": "stdio"
    }
  }
}
```

**Important**: Replace the following placeholders:
- `/path/to/uv`: Full path to your uv binary (find with `which uv`)
- `/path/to/pg-mcp`: Full path to the cloned repository
- Database connection details in the `env` section

### 6. Restart Cline

After adding the configuration, restart VS Code or reload the Cline extension to pick up the new MCP server.

## Verification

Once configured, you should be able to use the following tools in Cline:

- **execute_query**: Run SQL queries against your database
- **list_tables**: List tables in a specific schema
- **describe_table**: Get detailed table structure information

Example usage in Cline:
```
List all tables in the public schema
```

```
Show me the structure of the users table
```

```
Execute this query: SELECT COUNT(*) FROM orders WHERE status = 'pending'
```

## Troubleshooting

### Common Issues

1. **"Not connected" error**: 
   - Verify the uv path is correct
   - Check that the working directory path is accurate
   - Ensure database credentials are correct

2. **"Failed to spawn" error**:
   - Make sure uv is installed and accessible
   - Verify the server.py file exists in the specified directory

3. **Database connection errors**:
   - Test database connectivity manually
   - Check firewall settings
   - Verify credentials and host accessibility

### Getting Help

- Check the server logs in Cline's output panel
- Test the server independently with `uv run mcp dev server.py`
- Verify database connectivity with a simple SQL client

## Security Notes

- Store sensitive database credentials securely
- Consider using read-only database users for SELECT-only access
- Review and approve SQL queries before execution in production environments
- Use environment variables instead of hardcoding credentials

## Available Tools

### execute_query
Execute SQL queries against your PostgreSQL database.

**Parameters:**
- `query` (string): The SQL query to execute

### list_tables
List all tables in a specified schema.

**Parameters:**
- `schema` (string, optional): Schema name (default: "public")

### describe_table
Get detailed information about a specific table.

**Parameters:**
- `table_name` (string): Name of the table to describe
- `schema` (string, optional): Schema name (default: "public")

## Resources

The server also provides MCP resources for schema information:

- `schema://tables`: Overview of all tables in the public schema
- `schema://table/{table_name}`: Detailed schema for a specific table
