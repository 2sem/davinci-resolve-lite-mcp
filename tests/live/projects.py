import os

from tests.live import (
    CTX,
    MARKER_FLAKE,
    SCRATCH,
    STILL_FLAKE,
    TMP,
    VID1,
    Skip,
    call,
    color_grab,
    err,
    fresh_group,
    goto_scratch,
    need,
    skip_if,
    src_required,
    test,
)


# ---- projects ----
@test("list_projects")
def _(): need(len(call("list_projects")["projects"]) >= 1)

@test("load_project")
def _(): err("load_project", name="__no_such_project__")  # destructive to switch; error-path

@test("get_project_info")
def _(): need(call("get_project_info")["framerate"])

@test("save_project")
def _(): need(call("save_project")["ok"])

@test("create_project")
def _(): raise Skip("would create an undeletable project")

@test("close_project")
def _(): raise Skip("would close the active project")

@test("export_project")
def _():
    p = os.path.join(TMP, "proj.drp")
    call("export_project", filePath=p); need(os.path.exists(p))

@test("import_project")
def _(): err("import_project", filePath="/nonexistent/x.drp")

@test("restore_project")
def _(): err("restore_project", filePath="/nonexistent/x")

@test("get_project_presets")
def _(): need("presets" in call("get_project_presets"))

@test("set_project_preset")
def _(): err("set_project_preset", name="__no_such_preset__")
