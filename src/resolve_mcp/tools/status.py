"""Status Resolve MCP tools."""


from . import register
from ._helpers import *


@register(
    "get_status",
    "Return Resolve product/version and the current project, timeline and page.",
    None,
)
def get_status(resolve, args):
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    timeline = project.GetCurrentTimeline() if project else None
    product = resolve.GetProductName()
    return {
        "product": product,
        "studio": "Studio" in (product or ""),
        "version": resolve.GetVersionString(),
        "currentPage": resolve.GetCurrentPage(),
        "project": project.GetName() if project else None,
        "timeline": timeline.GetName() if timeline else None,
    }


@register(
    "open_page",
    "Switch the Resolve UI to a page.",
    {
        "type": "object",
        "properties": {
            "page": {"type": "string", "enum": list(VALID_PAGES)},
        },
        "required": ["page"],
    },
)
def open_page(resolve, args):
    page = args.get("page")
    if page not in VALID_PAGES:
        raise ToolError(f"page must be one of {VALID_PAGES}")
    if not resolve.OpenPage(page):
        raise ToolError(f"OpenPage({page!r}) failed.")
    return {"ok": True, "page": page}


@register(
    "get_fairlight_presets",
    "List the names of available Fairlight audio mixing presets.",
    None,
)
def get_fairlight_presets(resolve, args):
    return {"presets": resolve.GetFairlightPresets() or []}


@register(
    "disable_background_tasks",
    "Disable all background tasks for the current Resolve session (e.g. "
    "auto-render caching), freeing up resources for a heavy scripted job.",
    None,
)
def disable_background_tasks(resolve, args):
    resolve.DisableBackgroundTasksForCurrentResolveSession()
    return {"ok": True}
