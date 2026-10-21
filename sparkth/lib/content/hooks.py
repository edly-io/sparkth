"""Hook through which a plugin contributes content another plugin publishes to an LMS.

A *content contributor* is a named producer of one LMS content block. A plugin that owns
content registers one; a plugin that publishes to an LMS resolves it **by name** and awaits the
builder registered under the publishing plugin's own name.

A contributor may also offer *options*, the choices an author picks between, such as which
activity to place. The publisher lists them and hands the chosen option's id back to the
builder.

The hook is keyed by plugin, so a plugin switched off for a user stops contributing: a
publishing plugin resolves contributors through :func:`enabled_content_contributors`, which
leaves out those of a disabled plugin. A plugin registers one contributor from its
``SparkthPlugin.__init__``::

    register_content_contributor(
        self, ContentContributor("pxc", "...", {"open-edx": build_pxc_block}, list_pxc_options)
    )
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import current_user_id
from sparkth.lib.content.exceptions import (
    ContentContributorUnavailableError,
    DuplicateContentContributorError,
    UnknownContentContributorError,
)
from sparkth.lib.db import session_scope
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin, disabled_plugin_names

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

    ``callback``, when set, is awaited by a publishing tool after it calls the builder, with the
    option id the builder was given. The tool awaits it once it has created the block in the
    course and before it writes the block's attributes. A block whose attribute write then fails
    still counts as placed, since the caller may write its attributes again with another tool.
    ``callback`` reports a failure by raising
    :class:`~sparkth.lib.content.exceptions.ContentPlacementError`.

    ``list_options``, ``callback`` and the builders must be module-level functions. Each
    construction of a plugin registers its contributor again, which is accepted only if the
    copies compare equal, and a closure or bound method would not.
    """

    name: str
    description: str
    builders: Mapping[str, Callable[[str, str | None], Awaitable[ContentBlock]]]
    list_options: Callable[[], Awaitable[list[ContentOption]]] | None = None
    callback: Callable[[str | None], Awaitable[None]] | None = None


# One content contributor per plugin, consumed by LMS-publishing plugins. Keyed by plugin
# instance, so constructing a plugin again registers it harmlessly. Register through
# register_content_contributor, which refuses a name another contributor already claims.
LMS_CONTENT_CONTRIBUTORS: PluginHook[ContentContributor] = PluginHook()


def register_content_contributor(plugin: SparkthPlugin, contributor: ContentContributor) -> None:
    """Register ``plugin``'s ``contributor`` on the ``LMS_CONTENT_CONTRIBUTORS`` hook.

    Call this from a plugin's ``__init__``, passing ``self``. The hook records the plugin, so
    that plugin's switches decide whether the contributor is offered. A plugin has one
    contributor: registering one under another name from the same instance replaces the first.

    A plugin is constructed more than once in a single process — the loader builds it, and its
    own tests build their own instances — so each construction registers the same contributor
    again. An *equal* contributor from a plugin of the same name is accepted, and the copies fold
    into one when read. A contributor claiming a registered name with a different value, or
    from a different plugin, raises
    :class:`~sparkth.lib.content.exceptions.DuplicateContentContributorError`.

    Equality is what separates the two cases, so a contributor must stay a value with
    field-wise equality — that is why ``ContentContributor`` is a frozen dataclass rather
    than a class with identity semantics.
    """
    if any(
        registered.name == contributor.name and (owner.name != plugin.name or registered != contributor)
        for owner, registered in LMS_CONTENT_CONTRIBUTORS.iter_items()
    ):
        logger.error(
            "Content contributor '%s' collides with a different contributor already registered",
            contributor.name,
        )
        raise DuplicateContentContributorError(contributor.name)
    LMS_CONTENT_CONTRIBUTORS.add_item(plugin, contributor)
    logger.info("Registered content contributor '%s' for plugin '%s'", contributor.name, plugin.name)


async def _caller_disabled_plugins(session: AsyncSession) -> set[str]:
    """Plugin names switched off for the current caller.

    With no authenticated user bound, only the system-wide switch can apply.
    """
    user_id: int | None
    try:
        user_id = current_user_id()
    except NoAuthenticatedUser:
        logger.info("No authenticated user; applying only the system-wide plugin switch")
        user_id = None
    return await disabled_plugin_names(user_id, session)


async def enabled_content_contributors() -> dict[str, ContentContributor]:
    """The registered contributors the current caller may use, by name.

    Leaves out every contributor whose owning plugin is switched off for the caller, system-wide
    or by their own preference. A database error propagates.
    """
    async with session_scope() as session:
        disabled = await _caller_disabled_plugins(session)
    return {c.name: c for owner, c in LMS_CONTENT_CONTRIBUTORS.iter_items() if owner.name not in disabled}


async def enabled_content_contributor(name: str) -> ContentContributor:
    """The contributor registered as ``name``, if its plugin is switched on for the current caller.

    The switches are read only once the name is found. A database error propagates.

    Raises:
        UnknownContentContributorError: No contributor is registered as ``name``.
        ContentContributorUnavailableError: Its plugin is switched off for the caller.
    """
    owned = next(((owner, c) for owner, c in LMS_CONTENT_CONTRIBUTORS.iter_items() if c.name == name), None)
    if owned is None:
        raise UnknownContentContributorError(name)
    owner, contributor = owned
    async with session_scope() as session:
        disabled = await _caller_disabled_plugins(session)
    if owner.name in disabled:
        raise ContentContributorUnavailableError(name)
    return contributor
