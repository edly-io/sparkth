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

# Opens the embed page and its assets in an opaque origin, however they are opened, so activity
# code can never read Sparkth's own storage.
PXC_SANDBOX_HEADERS = {"Content-Security-Policy": "sandbox allow-scripts allow-forms"}

# What a cross-origin action POST asks permission for before it sends its JSON body.
PXC_PREFLIGHT_HEADERS = {
    **PXC_CORS_HEADERS,
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Content-Type",
}

# The course and placement every author preview launches into. Fixed, so an author's Student
# and Author views share one placement and what one saves shows in the other.
PXC_PREVIEW_COURSE_ID = "sparkth-preview"
PXC_PREVIEW_PLACEMENT = "preview"

# Prefixed onto a Sparkth user id in a preview token, so it never equals an Open edX learner id.
PXC_PREVIEW_USER_PREFIX = "sparkth-"
