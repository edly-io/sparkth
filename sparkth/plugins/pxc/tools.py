"""The pxc MCP tools: the PXC contract, and building, listing and reading back activities.

Every tool that touches an author's activities reads the author from ``current_user_id()``.
No tool takes a user id, so the model can neither supply one nor forge one.
The tools need an authenticated chat session. Over the unauthenticated MCP endpoint they raise
``NoAuthenticatedUser``.
"""

import json

from pxc.lib.manifest_types import PxcActivityManifest

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.constants import PXC_ABOUT_EXAMPLE, PXC_ABOUT_FILES, PXC_ASSET_DIR, PXC_MAX_SOURCE_CHARS


async def pxc_about() -> dict[str, str]:
    """Explain how a PXC activity is built: its files, the manifest schema, the permission rules,
    and a complete worked example.

    Call this before writing any activity code, and follow its rules exactly.
    """
    example = activity_dir(PXC_ABOUT_EXAMPLE)
    files = "\n\n".join(
        f"--- {PXC_ABOUT_EXAMPLE}/{name} ---\n{(example / name).read_text(encoding='utf-8')}"
        for name in PXC_ABOUT_FILES
    )
    rules = (PXC_ASSET_DIR / "about.txt").read_text(encoding="utf-8").format(max_source_chars=PXC_MAX_SOURCE_CHARS)
    schema = json.dumps(PxcActivityManifest.model_json_schema(), indent=2)
    return {"about": f"{rules}\n\n--- manifest JSON schema ---\n{schema}\n\n{files}"}
