"""MCP server — FastMCP initialisation and run entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# When run as script, add parent to path so mcp_server package is importable
_pkg_root = Path(__file__).resolve().parent.parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from mcp_server.auth import resolve_expected_admin_token
from mcp_server.tools import save_reservation

load_dotenv()

mcp = FastMCP("parking-storage")
mcp.tool()(save_reservation)


def _main() -> None:
    resolve_expected_admin_token()  # fail fast if token is missing
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_SERVER_PORT", "8001")),
        path=os.getenv("MCP_SERVER_PATH", "/mcp"),
    )


if __name__ == "__main__":
    _main()
