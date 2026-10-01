from pathlib import Path

# Where the bundled activity sources live, one directory per activity type. One sample ships
# today and is served for every request; an authoring module comes later.
PXC_ACTIVITY_ROOT = Path(__file__).parent / "activities"

# The XBlock category the Open edX course holds. Fixed rather than configurable: it must equal
# the name of the entry point the XBlock registers, and a configurable value could drift out of
# sync with the installed package (L6).
PXC_BLOCK_CATEGORY = "pxc"

# The embed page's origin is opaque, so everything it fetches from this plugin is cross-origin.
# Any origin is allowed because these routes authenticate by launch token, never by cookie.
PXC_CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}

# What a cross-origin action POST asks permission for before it sends its JSON body.
PXC_PREFLIGHT_HEADERS = {
    **PXC_CORS_HEADERS,
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Content-Type",
}
