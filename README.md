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