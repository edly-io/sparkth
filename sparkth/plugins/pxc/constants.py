from pathlib import Path

# Bundled activity sources, one directory per activity type.
PXC_ACTIVITY_ROOT = Path(__file__).parent / "activities"

# Must equal the entry point name the XBlock registers, so it is not configurable.
PXC_BLOCK_CATEGORY = "pxc"

# Any origin is allowed: the embed page's origin is opaque, and these routes use launch tokens.
PXC_CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}

# Gives the embed page and its assets an opaque origin, so activities cannot read Sparkth storage.
PXC_SANDBOX_HEADERS = {"Content-Security-Policy": "sandbox allow-scripts allow-forms"}

# Socket close codes for a refusal: 4000 plus the matching HTTP status.
PXC_CLOSE_INVALID_TOKEN = 4401
PXC_CLOSE_ACTIVITY_NOT_FOUND = 4404

# Preflight response for the cross-origin action POST.
PXC_PREFLIGHT_HEADERS = {
    **PXC_CORS_HEADERS,
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Content-Type",
}
