"""Hook through which a plugin contributes content another plugin publishes to an LMS.

A *content contributor* is a named producer of one LMS content block. A plugin that owns
content registers one; a plugin that publishes to an LMS resolves it **by name** and awaits the
builder registered under the publishing plugin's own name.

A contributor may also offer *options*, the choices an author picks between, such as which
activity to place. The publisher lists them and hands the chosen option's id back to the
builder.

A plugin registers from its ``SparkthPlugin.__init__``::

    register_content_contributor(
        ContentContributor("pxc", "...", {"open-edx": build_pxc_block}, list_pxc_options)
    )
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sparkth.lib.content.exceptions import DuplicateContentContributorError
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

    ``builders`` is keyed by the publishing plugin's own name, so its keys are the LMSes this
    contributor targets. Each builder is awaited with the destination course id and the chosen
    option's id. The option id is ``None`` when the caller chose none, and a builder then builds
    its default block. A builder reports a failure, including an option the caller may not use,
    by raising :class:`~sparkth.lib.content.exceptions.ContentBuildError`.

    ``list_options``, when set, returns the options the authenticated caller may choose from.
    A contributor whose options depend on the caller reads the caller with
    :func:`sparkth.lib.auth.current_user_id` itself, so a publishing tool never handles
    identity. Leave it ``None`` for a contributor that builds one kind of block; a publishing
    tool then refuses any option id.

    ``list_options`` and the builders must be module-level functions. Re-registering an equal
    contributor is a no-op only if they compare equal across constructions, and a closure or
    bound method would not.
    """

    name: str
    description: str
    builders: Mapping[str, Callable[[str, str | None], Awaitable[ContentBlock]]]
    list_options: Callable[[], Awaitable[list[ContentOption]]] | None = None


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
    raises :class:`~sparkth.lib.content.exceptions.DuplicateContentContributorError`, which
    is the collision worth failing on: a publishing tool resolves by name, so two unequal
    contributors sharing one name would silently build whichever registered first.

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
