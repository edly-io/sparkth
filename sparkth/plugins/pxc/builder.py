"""Build an author's activity from the files an agent wrote, inside the web process."""

from pxc.lib.manifest_types import PxcActivityManifest
from pydantic import ValidationError

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.constants import PXC_BUILD_ERROR_LIMIT
from sparkth.plugins.pxc.exceptions import PxcManifestInvalid

logger = get_logger(__name__)


def _manifest_rule_violations(manifest: PxcActivityManifest) -> list[str]:
    """What a schema-valid manifest still gets wrong for a generated activity.

    An activity is exactly its two scripts, so ``assets`` is refused. The sandbox world imports
    only ``pxc:sandbox/state``, so a declared capability could never be used. The file names
    are the ones the build writes.
    """
    violations = []
    if manifest.assets:
        violations.append('"assets" is not supported: an activity is exactly ui.js and sandbox.js')
    if manifest.capabilities:
        violations.append('"capabilities" is not supported: the sandbox can import only pxc:sandbox/state')
    if manifest.ui != "ui.js":
        violations.append('"ui" must be "ui.js"')
    if manifest.sandbox != "sandbox.wasm":
        violations.append('"sandbox" must be "sandbox.wasm"')
    return violations


def validate_manifest(manifest: dict[str, object], activity_id: str) -> dict[str, object]:
    """The manifest to write for this activity, with ``name`` set to its id.

    The server owns the name: it is the id the activity is stored and launched under.

    Raises:
        PxcManifestInvalid: naming every problem found, for the agent to fix.
    """
    named = {**manifest, "name": activity_id}
    try:
        parsed = PxcActivityManifest.model_validate(named)
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'manifest'}: {error['msg']}"
            for error in err.errors(include_url=False)
        )
        logger.info("Refused the manifest of PXC activity %s: %s", activity_id, problems)
        raise PxcManifestInvalid(
            f"manifest.json does not match the PXC manifest schema: {problems}"[:PXC_BUILD_ERROR_LIMIT]
        ) from err
    violations = _manifest_rule_violations(parsed)
    if violations:
        raise PxcManifestInvalid("manifest.json breaks the build's rules: " + "; ".join(violations))
    return named
