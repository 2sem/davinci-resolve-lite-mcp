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


@test("list_storage_volumes")
def _(): need("volumes" in call("list_storage_volumes"))

@test("browse_storage")
def _(): need("files" in call("browse_storage", path=os.path.expanduser("~/Movies")))

@test("add_storage_items_to_pool")
def _(): need(call("add_storage_items_to_pool", paths=["/nonexistent/x.mov"])["count"] == 0)

@test("reveal_in_storage")
def _():
    vols = call("list_storage_volumes")["volumes"]
    if not vols:
        raise Skip("no mounted volumes")
    try:
        need(call("reveal_in_storage", path=vols[0])["ok"])
    except AssertionError:
        raise Skip("RevealInStorage returned false")
