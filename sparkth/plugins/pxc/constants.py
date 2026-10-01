import os
from pathlib import Path

# Where the bundled activity sources live, one directory per activity type. One sample ships
# today and is served for every request; an authoring module comes later.
PXC_ACTIVITY_ROOT = Path(__file__).parent / "activities"

# The XBlock category the Open edX course holds. Fixed rather than configurable: it must equal
# the name of the entry point the XBlock registers, and a configurable value could drift out of
# sync with the installed package (L6).
PXC_BLOCK_CATEGORY = "pxc"

# The embed page's origin is opaque, so everything it fetches from this plugin is cross-origin.
# Any origin is allowed because these learner routes authenticate by launch token, never by cookie.
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

# The longest build error handed back to the agent, in characters. Compiler and smoke output
# keep their end, where the cause is; a manifest schema message keeps its start.
PXC_BUILD_ERROR_LIMIT = int(os.getenv("PXC_BUILD_ERROR_LIMIT", "4000"))

# The longest ui.js or sandbox.js an agent may submit, in characters, refused before any compile.
PXC_MAX_SOURCE_CHARS = int(os.getenv("PXC_MAX_SOURCE_CHARS", "200000"))

# Prefixed onto a Sparkth user id in a preview token, so it never equals an Open edX learner id.
PXC_PREVIEW_USER_PREFIX = "sparkth-"

# The course, placement and learner id the build's smoke test reads state as.
PXC_SMOKE_CONTEXT_ID = "smoke"

# The WIT world every generated activity compiles against: the bundled sample's. That world
# imports only pxc:sandbox/state, so a generated sandbox can call nothing else on the host.
PXC_SANDBOX_WIT = PXC_ACTIVITY_ROOT / "mcq" / "pxc.wit"

# The pxc plugin's prompt and contract texts.
PXC_ASSET_DIR = Path(__file__).parent / "assets"

# The bundled activity pxc_about hands the agent as its worked example, and the files it shows.
PXC_ABOUT_EXAMPLE = "mcq"
PXC_ABOUT_FILES = ("pxc.wit", "manifest.json", "sandbox.js", "ui.js")
