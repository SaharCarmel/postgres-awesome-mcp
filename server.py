#!/usr/bin/env python3
"""
PostgreSQL MCP Server

A Model Context Protocol server that provides tools for querying PostgreSQL
databases.
"""

import os
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
    """Database connection context for the server."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Initialize database connection pool."""
        # Get connection parameters from environment
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        database = os.getenv("POSTGRES_DATABASE", "postgres")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        
        # Create connection pool
        self.pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=1,
            max_size=10,
            command_timeout=30
        )
        
    async def disconnect(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()


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
async def execute_query(query: str, ctx: Context) -> Dict[str, Any]:
    """
    Execute a SQL query against the PostgreSQL database.
    
    Args:
        query: The SQL query to execute
        ctx: MCP context containing database connection
        
    Returns:
        Dictionary containing query results, row count, and metadata
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    if not db_context.pool:
        return {"error": "Database connection not available"}
    
    try:
        async with db_context.pool.acquire() as conn:
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
                    "query": query
                }
            else:
                # For INSERT, UPDATE, DELETE, etc.
                result = await conn.execute(query)
                
                return {
                    "success": True,
                    "message": result,
                    "query": query
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query
        }


@mcp.tool()
async def list_tables(ctx: Context, schema: str = "public") -> Dict[str, Any]:
    """
    List all tables in the specified schema.
    
    Args:
        ctx: MCP context containing database connection
        schema: Database schema name (default: public)
        
    Returns:
        Dictionary containing list of tables and their basic info
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    if not db_context.pool:
        return {"error": "Database connection not available"}
    
    try:
        async with db_context.pool.acquire() as conn:
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
                "count": len(tables)
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "schema": schema
        }


@mcp.tool()
async def describe_table(table_name: str, ctx: Context,
                         schema: str = "public") -> Dict[str, Any]:
    """
    Get detailed information about a specific table including columns, 
    types, and constraints.
    
    Args:
        table_name: Name of the table to describe
        ctx: MCP context containing database connection
        schema: Database schema name (default: public)
        
    Returns:
        Dictionary containing table structure information
    """
    db_context: DatabaseContext = ctx.request_context.lifespan_context
    
    if not db_context.pool:
        return {"error": "Database connection not available"}
    
    try:
        async with db_context.pool.acquire() as conn:
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
                "constraints": [dict(const) for const in constraints]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "table_name": table_name,
            "schema": schema
        }


@mcp.resource("schema://tables")
async def get_all_tables_schema() -> str:
    """
    Provide a comprehensive schema overview of all tables as a resource.
    """
    # Get database context from the server's lifespan context
    db_context: DatabaseContext = mcp.request_context.lifespan_context
    
    if not db_context.pool:
        return "Error: Database connection not available"
    
    try:
        async with db_context.pool.acquire() as conn:
            query = """
                SELECT 
                    t.table_name,
                    t.table_type,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c 
                    ON t.table_name = c.table_name 
                    AND t.table_schema = c.table_schema
                WHERE t.table_schema = 'public'
                ORDER BY t.table_name, c.ordinal_position
            """
            
            rows = await conn.fetch(query)
            
            # Format as readable schema
            schema_text = "# Database Schema Overview\n\n"
            current_table = None
            
            for row in rows:
                if row['table_name'] != current_table:
                    current_table = row['table_name']
                    schema_text += f"## Table: {current_table}\n"
                    schema_text += f"Type: {row['table_type']}\n\n"
                    schema_text += "| Column | Type | Nullable | Default |\n"
                    schema_text += "|--------|------|----------|----------|\n"
                
                if row['column_name']:  # Only if there are columns
                    nullable = "Yes" if row['is_nullable'] == 'YES' else "No"
                    default = row['column_default'] or "None"
                    schema_text += f"| {row['column_name']} | {row['data_type']} | {nullable} | {default} |\n"
            
            return schema_text
            
    except Exception as e:
        return f"Error retrieving schema: {str(e)}"


@mcp.resource("schema://table/{table_name}")
async def get_table_schema(table_name: str) -> str:
    """
    Provide detailed schema information for a specific table as a resource.
    """
    # Get database context from the server's lifespan context
    db_context: DatabaseContext = mcp.request_context.lifespan_context
    
    if not db_context.pool:
        return "Error: Database connection not available"
    
    try:
        async with db_context.pool.acquire() as conn:
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
            
            columns = await conn.fetch(columns_query, "public", table_name)
            
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
            
            constraints = await conn.fetch(constraints_query, "public", table_name)
            
            result = {
                "success": True,
                "table_name": table_name,
                "schema": "public",
                "columns": [dict(col) for col in columns],
                "constraints": [dict(const) for const in constraints]
            }
    except Exception as e:
        return f"Error: {str(e)}"
    
    if not result.get("success"):
        return f"Error: {result.get('error', 'Unknown error')}"
    
    # Format as readable text
    schema_text = f"# Table: {table_name}\n\n"
    schema_text += "## Columns\n\n"
    schema_text += "| Column | Type | Nullable | Default | Max Length | Precision | Scale |\n"
    schema_text += "|--------|------|----------|---------|------------|-----------|-------|\n"
    
    for col in result["columns"]:
        nullable = "Yes" if col['is_nullable'] == 'YES' else "No"
        default = col['column_default'] or "None"
        max_len = col['character_maximum_length'] or "N/A"
        precision = col['numeric_precision'] or "N/A"
        scale = col['numeric_scale'] or "N/A"
        
        schema_text += f"| {col['column_name']} | {col['data_type']} | {nullable} | {default} | {max_len} | {precision} | {scale} |\n"
    
    if result["constraints"]:
        schema_text += "\n## Constraints\n\n"
        schema_text += "| Constraint | Type | Column |\n"
        schema_text += "|------------|------|--------|\n"
        
        for const in result["constraints"]:
            schema_text += f"| {const['constraint_name']} | {const['constraint_type']} | {const['column_name']} |\n"
    
    return schema_text


@mcp.prompt()
def sql_query_helper(table_name: str, operation: str = "SELECT") -> str:
    """
    Generate a helpful prompt for writing SQL queries against a specific table.
    
    Args:
        table_name: The table to query
        operation: Type of SQL operation (SELECT, INSERT, UPDATE, DELETE)
    """
    return f"""
Help me write a {operation} query for the '{table_name}' table.

Please consider:
1. The table structure and column types
2. Appropriate WHERE clauses for filtering
3. Proper JOIN syntax if multiple tables are involved
4. Best practices for {operation} operations

Table: {table_name}
Operation: {operation}

What would you like to accomplish with this query?
"""


if __name__ == "__main__":
    # Run the server
    mcp.run()
