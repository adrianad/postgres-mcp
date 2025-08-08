## Minimal Postgres MCP Server

This is a minimal implementation of a Postgres MCP server focused purely on SQL execution. It provides only the `execute_sql` tool for running queries.

## MCP Server API

The [MCP standard](https://modelcontextprotocol.io/) defines various types of endpoints: Tools, Resources, Prompts, and others.

This server provides functionality via [MCP tools](https://modelcontextprotocol.io/docs/concepts/tools) alone.
We chose this approach because the [MCP client ecosystem](https://modelcontextprotocol.io/clients) has widespread support for MCP tools.
This contrasts with the approach of other Postgres MCP servers, including the [Reference Postgres MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/postgres), which use [MCP resources](https://modelcontextprotocol.io/docs/concepts/resources) to expose schema information.


Postgres MCP Pro Tools:

| Tool Name | Description |
|-----------|-------------|
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

## SSE Server Mode

If your MCP client only supports SSE transport, you can run the server in SSE mode:

```bash
DOCKER_BUILDKIT=1 docker build -t postgres-mcp-minimal .
docker run -d -p 8000:8000 --name postgres-mcp-minimal \
  -e DATABASE_URI="postgresql://username:password@host:port/database" \
  postgres-mcp-minimal --access-mode=restricted --transport=sse
```

Then configure your MCP client to connect via SSE:

```json
{
  "mcpServers": {
    "postgres": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

**Important**: The SSE endpoint is at `/sse`, not the root path. If you're using a different port or host, adjust the URL accordingly:
```json
{
  "mcpServers": {
    "postgres": {
      "type": "sse",
      "url": "http://your-host:8003/sse"
    }
  }
}
```