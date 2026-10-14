"""The pxc MCP tools: the PXC contract, building, listing, reading back and updating activities, and
reading a preview's failed actions.

The tools need an authenticated chat session. Over the unauthenticated MCP endpoint they raise
``NoAuthenticatedUser``.
"""

import json

from pxc.lib.manifest_types import PxcActivityManifest

from sparkth.lib.auth import current_user_id
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir, parse_activity_id, preview_url
from sparkth.plugins.pxc.builder import build_activity, update_activity
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_ASSET_DIR
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcManifestInvalid
from sparkth.plugins.pxc.revisions import live_revision
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import get_owned_activity, list_action_failures, list_owned_activities

logger = get_logger(__name__)


async def pxc_about() -> dict[str, str]:
    """Explain how a PXC activity is built: its files, the manifest schema and the permission rules.

    Call this before writing any activity code, and follow its rules exactly.
    """
    rules = (
        (PXC_ASSET_DIR / "about.txt")
        .read_text(encoding="utf-8")
        .format(max_source_chars=get_pxc_settings().max_source_chars)
    )
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
        logger.info("Refused manifest text that is not JSON: %s", err)
        raise PxcManifestInvalid(f"manifest is not valid JSON: {err}") from err
    if not isinstance(parsed, dict):
        logger.info("Refused a JSON manifest of type %s", type(parsed).__name__)
        raise PxcManifestInvalid(f"manifest must be a JSON object, got {type(parsed).__name__}")
    return parsed


async def pxc_build_activity(
    title: str, description: str, manifest: dict[str, object] | str, ui_js: str, sandbox_js: str
) -> dict[str, str]:
    """Build a new PXC activity from its three files and return its id and preview link.

    `title` and `description` are short and in the author's language. `manifest` is the
    manifest.json object (JSON text of that object is also accepted), `ui_js` the ui.js source,
    `sandbox_js` the sandbox.js source; follow `pxc_about` for all three. Every call creates a
    new activity; to change an existing one, use `pxc_update_activity`.

    If the build fails, the error explains why (an invalid manifest, a rejected import, compiler
    output, or getState or an action failing when the build ran it). Fix the files and call this again.
    """
    owner = current_user_id()
    source = ActivitySource(
        title=title,
        description=description,
        manifest=_manifest_object(manifest),
        ui_js=ui_js,
        sandbox_js=sandbox_js,
    )
    activity = await build_activity(source, owner)
    return {"activity_id": str(activity.id), "preview_url": preview_url(activity.id)}


async def pxc_list_activities(limit: int | None = None) -> dict[str, list[dict[str, str | bool]]]:
    """List the author's most recent activities, newest first. Each activity comes with its preview link
    and whether it has ever been placed in a course (this is never cleared).

    Use this to find an activity's id or preview link from an earlier turn: results of earlier
    tool calls are not kept in the conversation. Leave `limit` unset to get the newest few; set
    it higher only when the activity you need is older than the ones returned.
    """
    owner = current_user_id()
    if limit is None:
        limit = get_pxc_settings().list_activities_limit
    async with session_scope() as session:
        activities = await list_owned_activities(session, owner, limit)
    return {
        "activities": [
            {
                "activity_id": str(activity.id),
                "title": activity.title,
                "created_at": activity.created_at.isoformat(),
                "preview_url": preview_url(activity.id),
                "placed": activity.placed_at is not None,
            }
            for activity in activities
        ]
    }


async def pxc_get_activity_source(activity_id: str) -> dict[str, object]:
    """Return one of the author's activities as the files it was built from.

    Use this before changing an activity: edit the files it returns and pass them to
    `pxc_update_activity`. Only the activity's own author can read it. `placed` says whether the
    activity has ever been placed in a course (this is never cleared); once it has, its fields may
    not be removed or change their type, scope or schema.
    """
    owner = current_user_id()
    async with session_scope() as session:
        activity = await get_owned_activity(session, parse_activity_id(activity_id), owner)
    directory = activity_dir(str(activity.id))
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
        "placed": activity.placed_at is not None,
    }


async def pxc_get_activity_failures(activity_id: str, limit: int | None = None) -> dict[str, list[dict[str, str]]]:
    """Return the actions that failed in the author's own preview of one activity, newest first.

    Call this when the author reports an issue with the activity (e.g. glitches, wrong scores,
    etc.). Failures of only the activity's current version are returned.

    Each failure has its `kind`:
    - "rejected": ui.js sent a value the action's schema in the manifest refuses. Fix ui.js or the
      schema.
    - "failed": sandbox.js threw, or wrote a value its field or event refuses. `error` is the
      sandbox's own message. Fix sandbox.js, or the field or event schema.

    Args:
        activity_id: The activity's id, as `pxc_build_activity` or `pxc_list_activities` returns it.
        limit: How many of the newest failures to return; leave it out for the default.
    """
    owner = current_user_id()
    parsed_id = parse_activity_id(activity_id)
    if limit is None:
        limit = get_pxc_settings().action_failure_limit
    async with session_scope() as session:
        await get_owned_activity(session, parsed_id, owner)
        failures = await list_action_failures(session, parsed_id, live_revision(activity_id), limit)
    return {
        "failures": [
            {
                "kind": failure.kind,
                "action": failure.action,
                "permission": failure.permission,
                "value": failure.value,
                "error": failure.error,
                "created_at": failure.created_at.isoformat(),
            }
            for failure in failures
        ]
    }


async def pxc_update_activity(
    activity_id: str, title: str, description: str, manifest: dict[str, object] | str, ui_js: str, sandbox_js: str
) -> dict[str, str]:
    """Update one of the author's activities in place from its edited files, keeping its id.

    Pass back all three files from `pxc_get_activity_source`, edited, with the title and
    description. The update reaches every course using the activity and cannot be undone, so get
    the author's confirmation first when it is placed.

    A draft accepts any change. A placed activity accepts only backward-compatible field changes:
    adding a field (never as a replacement for an existing one) or changing a default. Anything
    else needs a new activity; ask the author before building one.

    A failed update leaves the activity unchanged, unless it fails after the new files go live.
    """
    owner = current_user_id()
    parsed_id = parse_activity_id(activity_id)
    source = ActivitySource(
        title=title,
        description=description,
        manifest=_manifest_object(manifest),
        ui_js=ui_js,
        sandbox_js=sandbox_js,
    )
    await update_activity(parsed_id, source, owner)
    return {"activity_id": activity_id, "preview_url": preview_url(parsed_id)}
