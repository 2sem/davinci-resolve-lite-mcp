"""DaVinci Resolve (Lite) MCP server package.

A zero-dependency, stdlib-only MCP server that runs inside the DaVinci Resolve
scripting runtime and exposes the Resolve API over a localhost HTTP endpoint.

Entry point: ``resolve_mcp.server.main``. The repo ships a thin launcher
(``davinci_mcp_server.py``) that puts this package on sys.path and calls it.
"""

from .config import SERVER_NAME, SERVER_VERSION

__all__ = ["SERVER_NAME", "SERVER_VERSION"]
