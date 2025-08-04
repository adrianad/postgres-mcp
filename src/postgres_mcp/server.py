# ruff: noqa: B008
import argparse
import asyncio
import logging
import os
import signal
import sys
from enum import Enum
from typing import Any
from typing import List
from typing import Union

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .sql import DbConnPool
from .sql import SafeSqlDriver
from .sql import SqlDriver
from .sql import obfuscate_password

# Initialize FastMCP with default settings
mcp = FastMCP("postgres-mcp")


ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

logger = logging.getLogger(__name__)


class AccessMode(str, Enum):
    """SQL access modes for the server."""

    UNRESTRICTED = "unrestricted"  # Unrestricted access
    RESTRICTED = "restricted"  # Read-only with safety features


# Global variables
db_connection = DbConnPool()
current_access_mode = AccessMode.UNRESTRICTED
shutdown_in_progress = False


async def get_sql_driver() -> Union[SqlDriver, SafeSqlDriver]:
    """Get the appropriate SQL driver based on the current access mode."""
    base_driver = SqlDriver(conn=db_connection)

    if current_access_mode == AccessMode.RESTRICTED:
        logger.debug("Using SafeSqlDriver with restrictions (RESTRICTED mode)")
        return SafeSqlDriver(sql_driver=base_driver, timeout=30)  # 30 second timeout
    else:
        logger.debug("Using unrestricted SqlDriver (UNRESTRICTED mode)")
        return base_driver


def format_text_response(text: Any) -> ResponseType:
    """Format a text response."""
    return [types.TextContent(type="text", text=str(text))]


def format_error_response(error: str) -> ResponseType:
    """Format an error response."""
    return format_text_response(f"Error: {error}")




@mcp.tool(description="List objects in the public schema")
async def list_objects(
    object_type: str = Field(description="Object type: 'table', 'view', 'sequence', or 'extension'", default="table"),
) -> ResponseType:
    """List objects of a given type in the public schema."""
    try:
        sql_driver = await get_sql_driver()

        if object_type in ("table", "view"):
            table_type = "BASE TABLE" if object_type == "table" else "VIEW"
            rows = await SafeSqlDriver.execute_param_query(
                sql_driver,
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = {} AND table_type = {}
                ORDER BY table_name
                """,
                ["public", table_type],
            )
            objects = [row.cells["table_name"] for row in rows] if rows else []

        elif object_type == "sequence":
            rows = await SafeSqlDriver.execute_param_query(
                sql_driver,
                """
                SELECT sequence_name
                FROM information_schema.sequences
                WHERE sequence_schema = {}
                ORDER BY sequence_name
                """,
                ["public"],
            )
            objects = [row.cells["sequence_name"] for row in rows] if rows else []

        elif object_type == "extension":
            # Extensions are not schema-specific
            rows = await sql_driver.execute_query(
                """
                SELECT extname
                FROM pg_extension
                ORDER BY extname
                """
            )
            objects = [row.cells["extname"] for row in rows] if rows else []

        else:
            return format_error_response(f"Unsupported object type: {object_type}")

        return format_text_response(objects)
    except Exception as e:
        logger.error(f"Error listing objects: {e}")
        return format_error_response(str(e))


@mcp.tool(description="Get DDL for a database object in the public schema")
async def get_object_details(
    object_name: str = Field(description="Object name"),
    object_type: str = Field(description="Object type: 'table', 'view', 'sequence', or 'extension'", default="table"),
) -> ResponseType:
    """Get DDL for a database object in the public schema."""
    try:
        sql_driver = await get_sql_driver()

        if object_type == "table":
            # Use pg_dump-style DDL generation for tables
            rows = await SafeSqlDriver.execute_param_query(
                sql_driver,
                """
                SELECT 
                    'CREATE TABLE ' || schemaname || '.' || tablename || ' (' || E'\n' ||
                    string_agg(
                        '    ' || column_name || ' ' || 
                        CASE 
                            WHEN data_type = 'character varying' THEN 
                                CASE WHEN character_maximum_length IS NOT NULL 
                                     THEN 'varchar(' || character_maximum_length || ')'
                                     ELSE 'varchar' END
                            WHEN data_type = 'character' THEN 'char(' || character_maximum_length || ')'
                            WHEN data_type = 'numeric' THEN 
                                CASE WHEN numeric_precision IS NOT NULL AND numeric_scale IS NOT NULL
                                     THEN 'numeric(' || numeric_precision || ',' || numeric_scale || ')'
                                     ELSE 'numeric' END
                            ELSE data_type 
                        END ||
                        CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
                        CASE WHEN column_default IS NOT NULL THEN ' DEFAULT ' || column_default ELSE '' END,
                        ',' || E'\n'
                        ORDER BY ordinal_position
                    ) || E'\n' || ');' as ddl
                FROM information_schema.columns c
                JOIN pg_tables t ON c.table_name = t.tablename AND c.table_schema = t.schemaname
                WHERE c.table_schema = {} AND c.table_name = {}
                GROUP BY schemaname, tablename
                """,
                ["public", object_name],
            )

        elif object_type == "view":
            rows = await SafeSqlDriver.execute_param_query(
                sql_driver,
                """
                SELECT 'CREATE VIEW ' || schemaname || '.' || viewname || ' AS ' || E'\n' || definition as ddl
                FROM pg_views 
                WHERE schemaname = {} AND viewname = {}
                """,
                ["public", object_name],
            )

        elif object_type == "sequence":
            rows = await SafeSqlDriver.execute_param_query(
                sql_driver,
                """
                SELECT 'CREATE SEQUENCE ' || sequence_schema || '.' || sequence_name || 
                       CASE WHEN start_value IS NOT NULL THEN E'\n    START WITH ' || start_value ELSE '' END ||
                       CASE WHEN increment IS NOT NULL THEN E'\n    INCREMENT BY ' || increment ELSE '' END ||
                       ';' as ddl
                FROM information_schema.sequences
                WHERE sequence_schema = {} AND sequence_name = {}
                """,
                ["public", object_name],
            )

        elif object_type == "extension":
            rows = await SafeSqlDriver.execute_param_query(
                sql_driver,
                """
                SELECT 'CREATE EXTENSION ' || extname || 
                       CASE WHEN extversion IS NOT NULL THEN ' VERSION ''' || extversion || '''' ELSE '' END ||
                       ';' as ddl
                FROM pg_extension
                WHERE extname = {}
                """,
                [object_name],
            )

        else:
            return format_error_response(f"Unsupported object type: {object_type}")

        if rows and rows[0]:
            ddl = rows[0].cells["ddl"]
            return format_text_response(ddl)
        else:
            return format_error_response(f"{object_type} '{object_name}' not found")

    except Exception as e:
        logger.error(f"Error getting object details: {e}")
        return format_error_response(str(e))




# Query function declaration without the decorator - we'll add it dynamically based on access mode
async def execute_sql(
    sql: str = Field(description="SQL to run", default="all"),
) -> ResponseType:
    """Executes a SQL query against the database."""
    try:
        sql_driver = await get_sql_driver()
        rows = await sql_driver.execute_query(sql)  # type: ignore
        if rows is None:
            return format_text_response("No results")
        return format_text_response(list([r.cells for r in rows]))
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return format_error_response(str(e))










async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PostgreSQL MCP Server")
    parser.add_argument("database_url", help="Database connection URL", nargs="?")
    parser.add_argument(
        "--access-mode",
        type=str,
        choices=[mode.value for mode in AccessMode],
        default=AccessMode.UNRESTRICTED.value,
        help="Set SQL access mode: unrestricted (unrestricted) or restricted (read-only with protections)",
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse"],
        default="stdio",
        help="Select MCP transport: stdio (default) or sse",
    )
    parser.add_argument(
        "--sse-host",
        type=str,
        default="localhost",
        help="Host to bind SSE server to (default: localhost)",
    )
    parser.add_argument(
        "--sse-port",
        type=int,
        default=8000,
        help="Port for SSE server (default: 8000)",
    )

    args = parser.parse_args()

    # Store the access mode in the global variable
    global current_access_mode
    current_access_mode = AccessMode(args.access_mode)

    # Add the query tool with a description appropriate to the access mode
    if current_access_mode == AccessMode.UNRESTRICTED:
        mcp.add_tool(execute_sql, description="Execute any SQL query")
    else:
        mcp.add_tool(execute_sql, description="Execute a read-only SQL query")

    logger.info(f"Starting PostgreSQL MCP Server in {current_access_mode.upper()} mode")

    # Get database URL from environment variable or command line
    database_url = os.environ.get("DATABASE_URI", args.database_url)

    if not database_url:
        raise ValueError(
            "Error: No database URL provided. Please specify via 'DATABASE_URI' environment variable or command-line argument.",
        )

    # Initialize database connection pool
    try:
        await db_connection.pool_connect(database_url)
        logger.info("Successfully connected to database and initialized connection pool")
    except Exception as e:
        logger.warning(
            f"Could not connect to database: {obfuscate_password(str(e))}",
        )
        logger.warning(
            "The MCP server will start but database operations will fail until a valid connection is established.",
        )

    # Set up proper shutdown handling
    try:
        loop = asyncio.get_running_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))
    except NotImplementedError:
        # Windows doesn't support signals properly
        logger.warning("Signal handling not supported on Windows")
        pass

    # Run the server with the selected transport (always async)
    if args.transport == "stdio":
        await mcp.run_stdio_async()
    else:
        # Update FastMCP settings based on command line arguments
        mcp.settings.host = args.sse_host
        mcp.settings.port = args.sse_port
        await mcp.run_sse_async()


async def shutdown(sig=None):
    """Clean shutdown of the server."""
    global shutdown_in_progress

    if shutdown_in_progress:
        logger.warning("Forcing immediate exit")
        # Use sys.exit instead of os._exit to allow for proper cleanup
        sys.exit(1)

    shutdown_in_progress = True

    if sig:
        logger.info(f"Received exit signal {sig.name}")

    # Close database connections
    try:
        await db_connection.close()
        logger.info("Closed database connections")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

    # Exit with appropriate status code
    sys.exit(128 + sig if sig is not None else 0)
