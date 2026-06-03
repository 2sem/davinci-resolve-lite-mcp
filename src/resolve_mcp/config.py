"""Static configuration and environment-derived constants."""

import os

SERVER_NAME = "davinci-resolve-lite-mcp"
SERVER_VERSION = "0.13.1"
PROTOCOL_VERSION = "2025-06-18"

DEFAULT_HOST = os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("DAVINCI_MCP_PORT", "8765"))
PORT_SCAN_RANGE = 20  # if DEFAULT_PORT is busy, try the next N ports

LOG_FILENAME = "davinci-resolve-lite-mcp.log"
