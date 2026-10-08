from pathlib import Path

# Bundled activity sources, one directory per activity type.
PXC_ACTIVITY_ROOT = Path(__file__).parent / "activities"

# Must equal the entry point name the XBlock registers, so it is not configurable.
PXC_BLOCK_CATEGORY = "pxc"

# Any origin is allowed: the embed page's origin is opaque, and learner routes use launch tokens.
PXC_CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}

# Gives the embed page and its assets an opaque origin, so activities cannot read Sparkth storage.
PXC_SANDBOX_HEADERS = {"Content-Security-Policy": "sandbox allow-scripts allow-forms"}

# Socket close codes for a refusal: 4000 plus the matching HTTP status.
PXC_CLOSE_INVALID_TOKEN = 4401
PXC_CLOSE_ACTIVITY_NOT_FOUND = 4404

# Preflight response for the cross-origin action POST, cached by the browser for a day.
PXC_PREFLIGHT_HEADERS = {
    **PXC_CORS_HEADERS,
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
}

# The course and placement every author preview launches into. Fixed, so an author's Student
# and Author views share one placement and what one saves shows in the other.
PXC_PREVIEW_COURSE_ID = "sparkth-preview"
PXC_PREVIEW_PLACEMENT = "preview"

# Prefixed onto a Sparkth user id in a preview token, so it never equals an Open edX learner id.
PXC_PREVIEW_USER_PREFIX = "sparkth-"
