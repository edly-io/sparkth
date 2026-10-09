"""Environment-backed settings for the PXC plugin.

Only ``PXC_``-prefixed variables belong here, read through the same env files and in the same
precedence order as the core ``Settings`` class — which is what ``sparkth.lib.settings``
requires of a plugin that defines its own settings, and what makes a value set in ``.env`` or
``.env.local`` actually reach this plugin.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from sparkth.lib.settings import ENV_FILES


class PxcSettings(BaseSettings):
    """The PXC plugin's configuration, one field per ``PXC_`` environment variable."""

    model_config = SettingsConfigDict(
        env_prefix="PXC_",
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Holds each activity's SQLite state file, its file storage under storage/, generated
    # activities under activities/<id>/ and build scratch under builds/.
    data_dir: Path = Path("./data/pxc")

    # Shared with the Open edX XBlock. The XBlock signs a launch token with it and this plugin
    # verifies that signature, which is what makes the learner's identity trustworthy rather
    # than client-asserted. Sensitive: set it in .env.local, never in .env. Empty fails closed.
    launch_secret: str = ""

    # How long a launch token stays valid. Short: it is minted per page render.
    launch_token_ttl_seconds: int = 300

    # The activity the "pxc" contributor places when the author chooses none. Any bundled
    # activity name; authors pick their own activities through the contributor's options.
    default_activity: str = "mcq"

    # The directory holding compile.mjs and the node_modules it compiles an author's activity with.
    toolchain_dir: Path = Path("./sparkth/plugins/pxc/builder/toolchain")

    # How long each step of an activity build (the compile, then the smoke test) may run.
    build_timeout_seconds: int = 120

    # How many activity builds may run at once in this process. Each compile peaks near 600 MB.
    # TODO: move activity builds to a dedicated worker container to make this scale.
    build_concurrency: int = 2

    # The longest build error handed back to the agent, in characters. Compiler and smoke output
    # keep their end, where the cause is; a manifest schema message keeps its start.
    build_error_limit: int = 4000

    # The most of a build step's stderr kept in memory, in bytes: the end of it, where the cause
    # is. The rest is read and dropped, so a step flooding stderr can neither block nor exhaust
    # memory.
    build_stderr_limit_bytes: int = 65536

    # The longest ui.js, sandbox.js or manifest (as JSON) an agent may submit, in characters,
    # refused before any compile.
    max_source_chars: int = 20000

    # The longest activity description an agent may submit, in characters.
    max_description_chars: int = 2000

    # How many of an author's newest activities reach the model: the pxc_list_activities default,
    # and the cap on the author's activities offered for placing in a course.
    list_activities_limit: int = 20


@lru_cache
def get_pxc_settings() -> PxcSettings:
    """The PXC plugin's settings, read once per process."""
    return PxcSettings()
