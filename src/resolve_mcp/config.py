"""Static configuration and environment-derived constants.

Host/port resolve from (highest priority first):

1. environment variables ``DAVINCI_MCP_HOST`` / ``DAVINCI_MCP_PORT``
2. a persistent JSON config file (see ``_config_candidates``)
3. the built-in defaults (``127.0.0.1`` / ``8765``)

When the port comes from (1) or (2) it is treated as **pinned**: the server
binds exactly that port and refuses to auto-increment, so the URL you register
with Claude never silently moves between launches. Only the bare default (3)
keeps the old scan-forward-if-busy behaviour.
"""

import json
import os

SERVER_NAME = "davinci-resolve-lite-mcp"
SERVER_VERSION = "0.17.0"
PROTOCOL_VERSION = "2025-06-18"

LOG_FILENAME = "davinci-resolve-lite-mcp.log"
CONFIG_FILENAME = "davinci-resolve-lite-mcp.config.json"

PORT_SCAN_RANGE = 20  # only when the port is NOT pinned (bare default)


def _real_home():
    """Real home dir even under the sandbox (HOME is redirected there)."""
    try:
        import pwd  # noqa: WPS433

        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:  # noqa: BLE001
        return os.path.expanduser("~")


def _config_candidates():
    """Config-file locations to try, first existing wins.

    ``DAVINCI_MCP_CONFIG`` is an EXCLUSIVE override: when set, it is the only
    path consulted, so a typo / missing / malformed file there falls back to the
    built-in defaults rather than silently picking up another persistent config
    (which would bind the server to an unexpected endpoint). Without it, search
    ``~/Movies`` — the only user-friendly directory the sandboxed Lite app is
    granted to read (same reason the logfile lives there; ``~/.config`` is
    OUTSIDE the sandbox so Lite cannot read it) — then the XDG path for the
    non-sandboxed Studio build, where it is conventional.
    """
    explicit = os.environ.get("DAVINCI_MCP_CONFIG")
    if explicit:
        return [explicit]
    home = _real_home()
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return [
        os.path.join(home, "Movies", CONFIG_FILENAME),
        os.path.join(xdg, SERVER_NAME, "config.json"),
    ]


def _load_config():
    """Return (settings_dict, path) for the first readable JSON config, else ({}, None)."""
    for path in _config_candidates():
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data, path
    return {}, None


_CONFIG, CONFIG_PATH = _load_config()


def _resolve_setting(env_name, config_key, default):
    """env var > config file > default. Returns (value, source).

    ``source`` is ``"env"``, ``"file"`` or ``"default"`` so callers can report
    exactly where a value came from (the env var wins even when a config file is
    also present, so a bare "pinned" flag would mislabel that case).
    """
    env = os.environ.get(env_name)
    if env:
        return env, "env"
    if config_key in _CONFIG:
        return _CONFIG[config_key], "file"
    return default, "default"


_host, _host_source = _resolve_setting("DAVINCI_MCP_HOST", "host", "127.0.0.1")
_port, PORT_SOURCE = _resolve_setting("DAVINCI_MCP_PORT", "port", 8765)

DEFAULT_HOST = str(_host)
DEFAULT_PORT = int(_port)
PORT_PINNED = PORT_SOURCE != "default"  # env or file → bind exactly, no scan

# The sandbox-friendly place to drop a config file (same dir as the logfile);
# shown in the startup banner so users can pin the port without the README.
RECOMMENDED_CONFIG_PATH = CONFIG_PATH or os.path.join(
    _real_home(), "Movies", CONFIG_FILENAME
)
