"""The pxc MCP tools: the PXC contract, and building, listing and reading back activities.

The tools need an authenticated chat session. Over the unauthenticated MCP endpoint they raise
``NoAuthenticatedUser``.
"""

import json

from pxc.lib.manifest_types import PxcActivityManifest

from sparkth.lib.auth import current_user_id
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import generated_activity_dir, parse_activity_id, preview_url
from sparkth.plugins.pxc.builder import build_activity
from sparkth.plugins.pxc.constants import PXC_ASSET_DIR, PXC_MAX_SOURCE_CHARS
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcManifestInvalid
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import get_owned_activity, list_owned_activities

logger = get_logger(__name__)


async def pxc_about() -> dict[str, str]:
    """Explain how a PXC activity is built: its files, the manifest schema and the permission rules.

    Call this before writing any activity code, and follow its rules exactly.
    """
    rules = (PXC_ASSET_DIR / "about.txt").read_text(encoding="utf-8").format(max_source_chars=PXC_MAX_SOURCE_CHARS)
    schema = json.dumps(PxcActivityManifest.model_json_schema(), indent=2)
    return {"about": f"{rules}\n\n--- manifest JSON schema ---\n{schema}"}


def _manifest_object(manifest: dict[str, object] | str) -> dict[str, object]:
    """The manifest as an object, parsed first when the model sent it as JSON text.

    Some models serialise a nested object argument as a string. Reading it here saves the agent
    a failed call, and text that is not a JSON object gets an error the agent can act on.

    Raises:
        PxcManifestInvalid: if the text is not JSON, or is JSON but not an object.
    """
    if isinstance(manifest, dict):
        return manifest
    try:
        parsed = json.loads(manifest)
    except json.JSONDecodeError as err:
        logger.info("pxc_build_activity refused manifest text that is not JSON: %s", err)
        raise PxcManifestInvalid(f"manifest is not valid JSON: {err}") from err
    if not isinstance(parsed, dict):
        logger.info("pxc_build_activity refused a JSON manifest of type %s", type(parsed).__name__)
        raise PxcManifestInvalid(f"manifest must be a JSON object, got {type(parsed).__name__}")
    return parsed


async def pxc_build_activity(
    title: str, description: str, manifest: dict[str, object] | str, ui_js: str, sandbox_js: str
) -> dict[str, str]:
    """Build a new PXC activity from its three files and return its id and preview link.

    `title` and `description` are short and in the author's language. `manifest` is the
    manifest.json object (JSON text of that object is also accepted), `ui_js` the ui.js source,
    `sandbox_js` the sandbox.js source; follow `pxc_about` for all three. Every call creates a
    new activity: an existing one never changes.

    If the build fails, the error explains why (an invalid manifest, a rejected import, compiler
    output, or the sandbox failing to start). Fix the files and call this again.
    """
    source = ActivitySource(
        title=title,
        description=description,
        manifest=_manifest_object(manifest),
        ui_js=ui_js,
        sandbox_js=sandbox_js,
    )
    activity = await build_activity(source, current_user_id())
    return {"activity_id": str(activity.id), "preview_url": preview_url(activity.id)}


async def pxc_list_activities() -> dict[str, list[dict[str, str]]]:
    """List the activities the author has built, newest first, each with its preview link.

    Use this to find an activity's id or preview link from an earlier turn: results of earlier
    tool calls are not kept in the conversation.
    """
    async with session_scope() as session:
        activities = await list_owned_activities(session, current_user_id())
    return {
        "activities": [
            {
                "activity_id": str(activity.id),
                "title": activity.title,
                "description": activity.description,
                "created_at": activity.created_at.isoformat(),
                "preview_url": preview_url(activity.id),
            }
            for activity in activities
        ]
    }


async def pxc_get_activity_source(activity_id: str) -> dict[str, object]:
    """Return one of the author's activities as the files it was built from.

    Use this before changing an activity: edit the files it returns and build them again with
    `pxc_build_activity`, which creates a new activity. Only the activity's own author can read
    it.
    """
    async with session_scope() as session:
        activity = await get_owned_activity(session, parse_activity_id(activity_id), current_user_id())
    directory = generated_activity_dir(str(activity.id))
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        ui_js = (directory / "ui.js").read_text(encoding="utf-8")
        sandbox_js = (directory / "sandbox.js").read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as err:
        logger.error("PXC activity %s has a row but its files cannot be read: %s", activity.id, err)
        raise PxcActivityNotFound(f"Unknown activity: {activity.id}") from err
    return {
        "activity_id": str(activity.id),
        "title": activity.title,
        "description": activity.description,
        "manifest": manifest,
        "ui_js": ui_js,
        "sandbox_js": sandbox_js,
    }
