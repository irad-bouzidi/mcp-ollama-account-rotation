"""Entry point for stdio MCP transport.
Used by local AI assistants (opencode, claude code, etc.) via docker compose exec.
"""
from app.mcp_server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
