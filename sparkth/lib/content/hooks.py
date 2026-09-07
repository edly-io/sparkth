"""Hook through which a plugin contributes content another plugin publishes to an LMS.

A *content contributor* is a named producer of one LMS content block. A plugin that owns
content registers one; a plugin that publishes to an LMS resolves it **by name** and awaits the
builder registered under the publishing plugin's own name.

A plugin registers from its ``SparkthPlugin.__init__``::

    register_content_contributor(ContentContributor("pxc", "...", {"open-edx": build_pxc_block}))
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


class ContentBuildError(Exception):
    """Raised by a :class:`ContentContributor`'s ``build`` when it cannot produce its block.

    A publishing tool resolves the failure through its own error contract (for example,
    Open edX's ``openedx_add_plugin_content`` returns an ``{"error": {...}}`` dict) instead of
    letting the exception propagate as a raw, unhandled failure.
    """


@dataclass(frozen=True)
class ContentContributor:
    """A named producer of one :class:`ContentBlock` per LMS it targets.

    ``description`` is human-facing: it is what a publishing tool lists
    back to an agent choosing a contributor.

    ``builders`` is keyed by the publishing plugin's own name, so its keys are the LMSes this
    contributor targets. Each is awaited with the destination course id and reports a failure
    to build by raising :class:`ContentBuildError`.
    """

    name: str
    description: str
    builders: Mapping[str, Callable[[str], Awaitable[ContentBlock]]]


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
