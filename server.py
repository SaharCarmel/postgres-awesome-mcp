#!/usr/bin/env python3
"""
PostgreSQL MCP Server

A Model Context Protocol server that provides tools for querying PostgreSQL
databases. Supports multiple named database connections.
"""

import os
import json
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from collections.abc import AsyncIterator

import asyncpg
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context

# Load environment variables
load_dotenv()

# Create the MCP server
mcp = FastMCP("PostgreSQL MCP Server")


class DatabaseContext:
    """Database connection context supporting multiple databases."""
    
    def __init__(self):
        self.pools: Dict[str, asyncpg.Pool] = {}
        self.default_database: Optional[str] = None
        self.config: Dict[str, Any] = {}
    
    async def connect(self):
        """Initialize database connection pools for all configured databases."""
        # Load database configuration
        await self._load_config()
        
        # Create connection pools for each database
        for db_id, db_config in self.config.get("databases", {}).items():
            try:
                pool = await asyncpg.create_pool(
                    host=db_config["host"],
                    port=db_config["port"],
                    database=db_config["database"],
                    user=db_config["user"],
                    password=db_config["password"],
                    min_size=1,
                    max_size=10,
                    command_timeout=30
                )
                self.pools[db_id] = pool
                print(f"Connected to database '{db_id}': {db_config['host']}:{db_config['port']}/{db_config['database']}")
            except Exception as e:
                print(f"Failed to connect to database '{db_id}': {str(e)}")
                
        # Set default database
        self.default_database = self.config.get("default_database")
        if self.default_database and self.default_database not in self.pools:
            print(f"Warning: Default database '{self.default_database}' not available")
            # Use first available database as default
            if self.pools:
                self.default_database = list(self.pools.keys())[0]
                print(f"Using '{self.default_database}' as default database")
    
    async def _load_config(self):
        """Load database configuration from file or environment variables."""
        config_file = os.getenv("POSTGRES_CONFIG_FILE", "databases.json")
        
        # Try to load from config file first
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
                return
            except Exception as e:
                print(f"Failed to load config file {config_file}: {str(e)}")
        
        # Fallback to environment variables (backward compatibility)
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        database = os.getenv("POSTGRES_DATABASE", "postgres")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        
        # Create single database config from environment
        self.config = {
            "databases": {
                "default": {
                    "host": host,
                    "port": port,
                    "database": database,
                    "user": user,
                    "password": password
                }
            },
            "default_database": "default"
        }
    
    async def _save_config(self):
        """Save current configuration to file."""
        config_file = os.getenv("POSTGRES_CONFIG_FILE", "databases.json")
        
        try:
            # Create a copy of config without sensitive data for logging
            safe_config = {
                "databases": {},
                "default_database": self.config.get("default_database")
            }
            
            for db_id, db_config in self.config.get("databases", {}).items():
                safe_config["databases"][db_id] = {
                    "host": db_config["host"],
                    "port": db_config["port"],
                    "database": db_config["database"],
                    "user": db_config["user"],
                    "password": "***"  # Hide password in logs
                }
            
            # Save full config to file
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            print(f"Configuration saved to {config_file}")
            
        except Exception as e:
            print(f"Failed to save config to {config_file}: {str(e)}")
            raise
    
    def get_pool(self, database_id: Optional[str] = None) -> Optional[asyncpg.Pool]:
        """Get connection pool for specified database or default."""
        if database_id is None:
            database_id = self.default_database
        
        if database_id is None:
            return None
            
        return self.pools.get(database_id)
    
    def get_available_databases(self) -> list[str]:
        """Get list of available database IDs."""
        return list(self.pools.keys())
        
    async def disconnect(self):
        """Close all database connection pools."""
        for db_id, pool in self.pools.items():
            await pool.close()
            print(f"Disconnected from database '{db_id}'")


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[DatabaseContext]:
    """Manage application lifecycle with database connections."""
    db_context = DatabaseContext()
    try:
        await db_context.connect()
        yield db_context
    finally:
        await db_context.disconnect()


# Set up the server with lifespan management
mcp = FastMCP("PostgreSQL MCP Server", lifespan=app_lifespan)


@mcp.tool()
async def execute_query(query: str, ctx: Context, database_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute a SQL query against the PostgreSQL database.
    
    Args:
        query: The SQL query to execute
        ctx: MCP context containing database connection
        database_id: Optional database identifier. If not provided, uses the default database.
        
    Returns:
        Dictionary containing query results, row count, and metadata
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    pool = db_context.get_pool(database_id)
    if not pool:
        available_dbs = db_context.get_available_databases()
        return {
            "error": f"Database connection not available for '{database_id or 'default'}'. Available databases: {available_dbs}"
        }
    
    try:
        async with pool.acquire() as conn:
            # Execute the query
            if query.strip().upper().startswith(('SELECT', 'WITH')):
                # For SELECT queries, fetch all results
                rows = await conn.fetch(query)
                
                # Convert rows to dictionaries
                results = [dict(row) for row in rows]
                
                return {
                    "success": True,
                    "results": results,
                    "row_count": len(results),
                    "query": query,
                    "database_id": database_id or db_context.default_database
                }
            else:
                # For INSERT, UPDATE, DELETE, etc.
                result = await conn.execute(query)
                
                return {
                    "success": True,
                    "message": result,
                    "query": query,
                    "database_id": database_id or db_context.default_database
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "database_id": database_id or db_context.default_database
        }


@mcp.tool()
async def list_tables(ctx: Context, schema: str = "public", database_id: Optional[str] = None) -> Dict[str, Any]:
    """
    List all tables in the specified schema.
    
    Args:
        ctx: MCP context containing database connection
        schema: Database schema name (default: public)
        database_id: Optional database identifier. If not provided, uses the default database.
        
    Returns:
        Dictionary containing list of tables and their basic info
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    pool = db_context.get_pool(database_id)
    if not pool:
        available_dbs = db_context.get_available_databases()
        return {
            "error": f"Database connection not available for '{database_id or 'default'}'. Available databases: {available_dbs}"
        }
    
    try:
        async with pool.acquire() as conn:
            query = """
                SELECT 
                    table_name,
                    table_type,
                    is_insertable_into,
                    is_typed
                FROM information_schema.tables 
                WHERE table_schema = $1
                ORDER BY table_name
            """
            
            rows = await conn.fetch(query, schema)
            tables = [dict(row) for row in rows]
            
            return {
                "success": True,
                "schema": schema,
                "tables": tables,
                "count": len(tables),
                "database_id": database_id or db_context.default_database
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "schema": schema,
            "database_id": database_id or db_context.default_database
        }


@mcp.tool()
async def describe_table(table_name: str, ctx: Context,
                         schema: str = "public", database_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed information about a specific table including columns, 
    types, and constraints.
    
    Args:
        table_name: Name of the table to describe
        ctx: MCP context containing database connection
        schema: Database schema name (default: public)
        database_id: Optional database identifier. If not provided, uses the default database.
        
    Returns:
        Dictionary containing table structure information
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    pool = db_context.get_pool(database_id)
    if not pool:
        available_dbs = db_context.get_available_databases()
        return {
            "error": f"Database connection not available for '{database_id or 'default'}'. Available databases: {available_dbs}"
        }
    
    try:
        async with pool.acquire() as conn:
            # Get column information
            columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns 
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """
            
            columns = await conn.fetch(columns_query, schema, table_name)
            
            # Get constraints information
            constraints_query = """
                SELECT 
                    tc.constraint_name,
                    tc.constraint_type,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                    AND tc.table_name = kcu.table_name
                WHERE tc.table_schema = $1 AND tc.table_name = $2
            """
            
            constraints = await conn.fetch(constraints_query, schema, table_name)
            
            return {
                "success": True,
                "table_name": table_name,
                "schema": schema,
                "columns": [dict(col) for col in columns],
                "constraints": [dict(const) for const in constraints],
                "database_id": database_id or db_context.default_database
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "table_name": table_name,
            "schema": schema,
            "database_id": database_id or db_context.default_database
        }


@mcp.tool()
async def list_databases(ctx: Context) -> Dict[str, Any]:
    """
    List all available database connections configured in this MCP server.
    
    Args:
        ctx: MCP context containing database connection
        
    Returns:
        Dictionary containing list of available databases and connection info
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    available_dbs = db_context.get_available_databases()
    
    database_info = []
    for db_id in available_dbs:
        if db_id in db_context.config.get("databases", {}):
            config = db_context.config["databases"][db_id]
            database_info.append({
                "id": db_id,
                "host": config["host"],
                "port": config["port"],
                "database": config["database"],
                "user": config["user"],
                "is_default": db_id == db_context.default_database
            })
    
    return {
        "success": True,
        "databases": database_info,
        "default_database": db_context.default_database,
        "count": len(available_dbs)
    }


@mcp.tool()
async def add_database(
    ctx: Context,
    database_id: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    set_as_default: bool = False,
    project_name: Optional[str] = None,
    project_description: Optional[str] = None,
    project_tags: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new database connection dynamically.
    
    Args:
        ctx: MCP context containing database connection
        database_id: Unique identifier for this database connection
        host: Database host address
        port: Database port number
        database: Database name
        user: Database username
        password: Database password
        set_as_default: Whether to set this as the default database
        project_name: Optional project name this database belongs to
        project_description: Optional project description
        project_tags: Optional comma-separated tags for project categorization
        
    Returns:
        Dictionary containing operation result
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    # Check if database_id already exists
    if database_id in db_context.pools:
        return {
            "success": False,
            "error": f"Database '{database_id}' already exists"
        }
    
    # Validate database_id format
    if not database_id.replace("_", "").replace("-", "").isalnum():
        return {
            "success": False,
            "error": "Database ID must contain only alphanumeric characters, underscores, and hyphens"
        }
    
    try:
        # Create connection pool for the new database
        pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=1,
            max_size=10,
            command_timeout=30
        )
        
        # Add to pools
        db_context.pools[database_id] = pool
        
        # Add to config
        if "databases" not in db_context.config:
            db_context.config["databases"] = {}
        
        db_context.config["databases"][database_id] = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "project": {
                "name": project_name,
                "description": project_description,
                "tags": project_tags.split(",") if project_tags else []
            } if project_name else None
        }
        
        # Set as default if requested or if no default exists
        if set_as_default or db_context.default_database is None:
            db_context.default_database = database_id
            db_context.config["default_database"] = database_id
        
        # Save updated config to file
        await db_context._save_config()
        
        print(f"Added database '{database_id}': {host}:{port}/{database}")
        
        return {
            "success": True,
            "message": f"Database '{database_id}' added successfully",
            "database_id": database_id,
            "is_default": database_id == db_context.default_database
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to add database '{database_id}': {str(e)}"
        }


@mcp.tool()
async def find_databases_by_project(
    ctx: Context,
    project_name: Optional[str] = None,
    project_tag: Optional[str] = None
) -> Dict[str, Any]:
    """
    Find databases associated with a specific project or tag.
    
    Args:
        ctx: MCP context containing database connection
        project_name: Optional project name to search for
        project_tag: Optional project tag to search for
        
    Returns:
        Dictionary containing matching databases with project info
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    matching_databases = []
    
    for db_id in db_context.get_available_databases():
        if db_id in db_context.config.get("databases", {}):
            config = db_context.config["databases"][db_id]
            project_info = config.get("project")
            
            # Check if this database matches the search criteria
            matches = False
            
            if project_info:
                # Match by project name
                if project_name and project_info.get("name") == project_name:
                    matches = True
                
                # Match by project tag
                if project_tag and project_tag in project_info.get("tags", []):
                    matches = True
                
                # If no search criteria provided, include all databases with project info
                if not project_name and not project_tag:
                    matches = True
            elif not project_name and not project_tag:
                # Include databases without project info if no criteria specified
                matches = True
            
            if matches:
                db_info = {
                    "id": db_id,
                    "host": config["host"],
                    "port": config["port"],
                    "database": config["database"],
                    "user": config["user"],
                    "is_default": db_id == db_context.default_database,
                    "project": project_info
                }
                matching_databases.append(db_info)
    
    return {
        "success": True,
        "databases": matching_databases,
        "count": len(matching_databases),
        "search_criteria": {
            "project_name": project_name,
            "project_tag": project_tag
        }
    }


@mcp.tool()
async def get_project_database(
    ctx: Context,
    project_name: str
) -> Dict[str, Any]:
    """
    Get the primary database for a specific project.
    
    Args:
        ctx: MCP context containing database connection
        project_name: Project name to find database for
        
    Returns:
        Dictionary containing the project's database info or error
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    # Find databases for this project
    project_databases = []
    
    for db_id in db_context.get_available_databases():
        if db_id in db_context.config.get("databases", {}):
            config = db_context.config["databases"][db_id]
            project_info = config.get("project")
            
            if project_info and project_info.get("name") == project_name:
                project_databases.append({
                    "id": db_id,
                    "host": config["host"],
                    "port": config["port"],
                    "database": config["database"],
                    "user": config["user"],
                    "is_default": db_id == db_context.default_database,
                    "project": project_info
                })
    
    if not project_databases:
        return {
            "success": False,
            "error": f"No database found for project '{project_name}'"
        }
    
    # Return the first database (primary) for the project
    primary_db = project_databases[0]
    
    return {
        "success": True,
        "database": primary_db,
        "project_name": project_name,
        "total_databases": len(project_databases)
    }


@mcp.tool()
async def remove_database(ctx: Context, database_id: str) -> Dict[str, Any]:
    """
    Remove a database connection.
    
    Args:
        ctx: MCP context containing database connection
        database_id: Database identifier to remove
        
    Returns:
        Dictionary containing operation result
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    # Check if database exists
    if database_id not in db_context.pools:
        return {
            "success": False,
            "error": f"Database '{database_id}' not found"
        }
    
    # Don't allow removing the last database
    if len(db_context.pools) == 1:
        return {
            "success": False,
            "error": "Cannot remove the last database connection"
        }
    
    try:
        # Close the connection pool
        pool = db_context.pools[database_id]
        await pool.close()
        
        # Remove from pools and config
        del db_context.pools[database_id]
        if database_id in db_context.config.get("databases", {}):
            del db_context.config["databases"][database_id]
        
        # Update default if necessary
        if db_context.default_database == database_id:
            # Set first available database as default
            if db_context.pools:
                db_context.default_database = list(db_context.pools.keys())[0]
                db_context.config["default_database"] = db_context.default_database
            else:
                db_context.default_database = None
                db_context.config["default_database"] = None
        
        # Save updated config to file
        await db_context._save_config()
        
        print(f"Removed database '{database_id}'")
        
        return {
            "success": True,
            "message": f"Database '{database_id}' removed successfully",
            "new_default": db_context.default_database
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to remove database '{database_id}': {str(e)}"
        }


# Note: Resources are simplified for this multi-database version
# They only work with the default database due to MCP resource limitations
@mcp.resource("schema://tables")
async def get_all_tables_schema() -> str:
    """
    Provide a comprehensive schema overview from the default database.
    Note: Resources cannot accept database_id parameter due to MCP limitations.
    """
    return "Resource access not available in multi-database mode. Use list_tables tool instead."


@mcp.resource("schema://table/{table_name}")
async def get_table_schema(table_name: str) -> str:
    """
    Provide detailed schema information for a specific table.
    Note: Resources cannot accept database_id parameter due to MCP limitations.
    """
    return f"Resource access not available in multi-database mode. Use describe_table tool for '{table_name}' instead."


@mcp.prompt()
def sql_query_helper(table_name: str, operation: str = "SELECT", database_id: Optional[str] = None) -> str:
    """
    Generate a helpful prompt for writing SQL queries against a specific table.
    
    Args:
        table_name: The table to query
        operation: Type of SQL operation (SELECT, INSERT, UPDATE, DELETE)
        database_id: Optional database identifier
    """
    db_info = f" in database '{database_id}'" if database_id else ""
    
    return f"""
Help me write a {operation} query for the '{table_name}' table{db_info}.

Please consider:
1. The table structure and column types
2. Appropriate WHERE clauses for filtering
3. Proper JOIN syntax if multiple tables are involved
4. Best practices for {operation} operations

Table: {table_name}
Operation: {operation}
Database: {database_id or 'default'}

What would you like to accomplish with this query?
"""


if __name__ == "__main__":
    # Run the server
    mcp.run()
