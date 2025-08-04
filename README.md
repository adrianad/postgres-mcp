## Minimal Postgres MCP Server

This is a minimal implementation of a Postgres MCP server focused on basic database querying and table inspection. It provides only the essential tools needed for a simple database bot.

## MCP Server API

The [MCP standard](https://modelcontextprotocol.io/) defines various types of endpoints: Tools, Resources, Prompts, and others.

This server provides functionality via [MCP tools](https://modelcontextprotocol.io/docs/concepts/tools) alone.
We chose this approach because the [MCP client ecosystem](https://modelcontextprotocol.io/clients) has widespread support for MCP tools.
This contrasts with the approach of other Postgres MCP servers, including the [Reference Postgres MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/postgres), which use [MCP resources](https://modelcontextprotocol.io/docs/concepts/resources) to expose schema information.


Postgres MCP Pro Tools:

| Tool Name | Description |
|-----------|-------------|
| `list_objects` | Lists database objects (tables, views, sequences, extensions) in the public schema. |
| `get_object_details` | Returns the DDL (CREATE statement) for a database object in the public schema. |
| `execute_sql` | Executes SQL statements on the database, with read-only limitations when connected in restricted mode. |

## Quick Start

First, build the Docker image from the local code:

```bash
DOCKER_BUILDKIT=1 docker build -t postgres-mcp-minimal .
```

Then add this configuration to your MCP client (e.g., Claude Desktop, Cursor, etc.):

```json
{
  "mcpServers": {
    "postgres": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--name",
        "postgres-mcp",
        "-e",
        "DATABASE_URI",
        "postgres-mcp-minimal",
        "--access-mode=restricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@host:port/database"
      }
    }
  }
}
```

Replace the `DATABASE_URI` with your actual PostgreSQL connection details.