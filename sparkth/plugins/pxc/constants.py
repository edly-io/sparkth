import os
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

# The longest build error handed back to the agent, in characters. Compiler and smoke output
# keep their end, where the cause is; a manifest schema message keeps its start.
PXC_BUILD_ERROR_LIMIT = int(os.getenv("PXC_BUILD_ERROR_LIMIT", "4000"))

# The longest ui.js or sandbox.js an agent may submit, in characters, refused before any compile.
PXC_MAX_SOURCE_CHARS = int(os.getenv("PXC_MAX_SOURCE_CHARS", "200000"))

# Prefixed onto a Sparkth user id in a preview token, so it never equals an Open edX learner id.
PXC_PREVIEW_USER_PREFIX = "sparkth-"

# The course, placement and learner id the build's smoke test reads state as.
PXC_SMOKE_CONTEXT_ID = "smoke"

# The WIT world every sandbox compiles against. It imports only pxc:sandbox/state, so a sandbox
# can call nothing else on the host.
PXC_SANDBOX_WIT = Path(__file__).parent / "builder" / "toolchain" / "pxc.wit"

# The exit status of the toolchain's compile.mjs when its packages are not installed.
PXC_COMPILE_TOOLCHAIN_MISSING = 2

# The pxc plugin's prompt and contract texts.
PXC_ASSET_DIR = Path(__file__).parent / "assets"

# The MCP category every pxc tool registers under, which the pxc-activity-builder chat job claims.
PXC_TOOL_CATEGORY = "pxc"

# The chat job that builds activities.
PXC_BUILDER_RESPONSIBILITY_NAME = "pxc-activity-builder"

# What the chat classifier reads to route a conversation to the activity builder.
PXC_ACTIVITY_BUILDER_SCOPE = (PXC_ASSET_DIR / "pxc_activity_building_scope.txt").read_text(encoding="utf-8").strip()

# Formatted by chat with current_datetime and refusal_message.
PXC_ACTIVITY_BUILDER_SYSTEM_PROMPT = (
    (PXC_ASSET_DIR / "pxc_activity_building_system_prompt.txt").read_text(encoding="utf-8").strip()
)

# The most of a build step's stderr kept in memory, in bytes: the end of it, where the cause is.
# The rest is read and dropped, so a step flooding stderr can neither block nor exhaust memory.
PXC_BUILD_STDERR_LIMIT_BYTES = int(os.getenv("PXC_BUILD_STDERR_LIMIT_BYTES", "65536"))

# The longest activity description an agent may submit, in characters.
PXC_MAX_DESCRIPTION_CHARS = int(os.getenv("PXC_MAX_DESCRIPTION_CHARS", "2000"))
