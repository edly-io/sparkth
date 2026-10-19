"""Hook through which a plugin contributes content another plugin publishes to an LMS.

A *content contributor* is a named producer of one LMS content block. A plugin that owns
content registers one; a plugin that publishes to an LMS resolves it **by name** and awaits the
builder registered under the publishing plugin's own name.

A contributor may also offer *options*, the choices an author picks between, such as which
activity to place. The publisher lists them and hands the chosen option's id back to the
builder.

A contributor names the plugin that owns it, so a plugin switched off for a user stops
contributing: a publishing plugin resolves contributors through
:func:`enabled_content_contributors`, which leaves out those of a disabled plugin.

A plugin registers from its ``SparkthPlugin.__init__``::

    register_content_contributor(
        ContentContributor(
            "pxc", "...", {"open-edx": build_pxc_block}, list_pxc_options, plugin_name=self.name
        )
    )
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.plugins.service import disabled_plugin_names
from sparkth.lib.auth import current_user_id
from sparkth.lib.content.exceptions import DuplicateContentContributorError
from sparkth.lib.db import session_scope
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.hooks import SingleNamedItemHook
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ContentBlock:
    """One content block to create in an LMS course.

    ``kind`` and ``attributes`` are opaque here; the publishing plugin defines what each means
    for its own LMS.
    """

    title: str
    kind: str
    attributes: Any = None


@dataclass(frozen=True)
class ContentOption:
    """One choice a contributor offers for the block it builds.

    ``id`` is what a publishing tool hands back to the builder as ``option_id``; ``label`` is
    what an agent shows the author.
    """

    id: str
    label: str


@dataclass(frozen=True)
class ContentContributor:
    """A named producer of one :class:`ContentBlock` per LMS it targets.

    ``description`` is human-facing: it is what a publishing tool lists
    back to an agent choosing a contributor.

    ``builders`` is keyed by the publishing plugin's (LMS's) own name, so its keys are the LMSes this
    contributor targets. A builder reports a failure by raising
    :class:`~sparkth.lib.content.exceptions.ContentBuildError`.

    ``list_options``, when set, returns the options the authenticated caller may choose from,
    and a publishing tool requires one of them: nothing is built by default. Leave it ``None``
    for a contributor that builds one kind of block; a publishing tool then refuses any option id.

    ``on_placed``, when set, is awaited with the option id the builder was given, once the
    publishing tool has created the block in the course and before it writes the block's
    attributes. A block whose attribute write then fails still counts as placed, since the caller
    may write its attributes again with another tool. ``on_placed`` reports a failure by raising
    :class:`~sparkth.lib.content.exceptions.ContentPlacementError`.

    ``plugin_name`` is the name of the plugin that owns this contributor. A contributor is
    offered to a user only while that plugin is enabled for them.

    ``list_options``, ``on_placed`` and the builders must be module-level functions.
    Re-registering an equal contributor is a no-op only if they compare equal across
    constructions, and a closure or bound method would not.
    """

    name: str
    description: str
    builders: Mapping[str, Callable[[str, str | None], Awaitable[ContentBlock]]]
    list_options: Callable[[], Awaitable[list[ContentOption]]] | None = None
    on_placed: Callable[[str | None], Awaitable[None]] | None = None
    plugin_name: str = field(kw_only=True)


# Content contributors, keyed by name. Consumed by LMS-publishing plugins.
LMS_CONTENT_CONTRIBUTORS: SingleNamedItemHook[ContentContributor] = SingleNamedItemHook()


def register_content_contributor(contributor: ContentContributor) -> None:
    """Register ``contributor`` on the ``LMS_CONTENT_CONTRIBUTORS`` hook.

    Call this from a plugin's ``__init__``. Registration happens as the plugin is
    constructed, straight into the hook a publishing tool resolves against.

    A plugin is constructed more than once in a single process — the loader builds it, and
    its own tests build their own instances — so each construction re-registers the same
    contributor. Re-registering an *equal* one is therefore a no-op, and the first
    registration is the one kept. Only a *different* contributor claiming a registered name
    raises :class:`~sparkth.lib.content.exceptions.DuplicateContentContributorError`.

    Equality is what separates the two cases, so a contributor must stay a value with
    field-wise equality — that is why ``ContentContributor`` is a frozen dataclass rather
    than a class with identity semantics.
    """
    registered = LMS_CONTENT_CONTRIBUTORS.get(contributor.name)
    if registered == contributor:
        return
    if registered is not None:
        logger.error(
            "Content contributor '%s' collides with a different contributor already registered",
            contributor.name,
        )
        raise DuplicateContentContributorError(contributor.name)
    LMS_CONTENT_CONTRIBUTORS.add_item(contributor)
    logger.info("Registered content contributor '%s'", contributor.name)


async def _caller_disabled_plugins(session: AsyncSession) -> set[str]:
    """Plugin names switched off for the current caller.

    With no authenticated user bound, only the system-wide switch can apply.
    """
    try:
        user_id = current_user_id()
    except NoAuthenticatedUser:
        logger.info("No authenticated user; applying only the system-wide plugin switch")
        return await disabled_plugin_names(None, session)
    return await disabled_plugin_names(user_id, session)


async def enabled_content_contributors() -> dict[str, ContentContributor]:
    """The registered contributors the current caller may use, by name.

    Leaves out every contributor whose owning plugin is switched off for the caller, system-wide
    or by their own preference. A database error propagates.
    """
    async with session_scope() as session:
        disabled = await _caller_disabled_plugins(session)
    return {name: c for name, c in LMS_CONTENT_CONTRIBUTORS.iter_items() if c.plugin_name not in disabled}
