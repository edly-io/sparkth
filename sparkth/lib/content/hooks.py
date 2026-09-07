"""Hook through which a plugin contributes content another plugin publishes to an LMS.

A *content contributor* is a named producer of one LMS content block. A plugin that owns
content registers one; a plugin that publishes to an LMS resolves it **by name** and awaits
its ``build``. Neither plugin imports the other, so the producer can be removed or replaced
without touching the publisher, and a second publisher (Canvas) can consume the same hook
with no change to the producer.

A plugin registers at module level in its ``plugin.py``::

    LMS_CONTENT_CONTRIBUTORS.add_item(ContentContributor("pxc", "...", build_pxc_block))

Module level, not the package ``__init__`` and not ``SparkthPlugin.__init__``: this is a flat
hook keyed by name, and both of those run more than once in a pytest session, which would
raise on the second registration.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sparkth.lib.hooks import SingleNamedItemHook


@dataclass(frozen=True)
class ContentBlock:
    """One content block to create in an LMS course.

    ``category`` is the LMS's block type (Open edX calls it the XBlock category, and it must
    appear in the course's Advanced Module List for anything but the built-in types).
    ``settings`` is applied to the block after creation; every value is carried as a string
    because that is what an XBlock's metadata holds.
    """

    category: str
    display_name: str
    settings: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ContentContributor:
    """A named producer of one :class:`ContentBlock`.

    ``build`` is awaited with the destination course id and returns the block to create. It is
    a callable field rather than a method to override, mirroring ``Tool(handler)`` on the
    ``MCP_TOOLS`` hook. ``description`` is human-facing: it is what a publishing tool lists
    back to an agent choosing a contributor. ``build`` reports its own failure to produce a
    block by raising :class:`~sparkth.lib.content.exceptions.ContentBuildError`; it must not
    raise anything else.
    """

    name: str
    description: str
    build: Callable[[str], Awaitable[ContentBlock]]


# Content contributors, keyed by name. Consumed by LMS-publishing plugins
# (sparkth/plugins/openedx/tools.py).
LMS_CONTENT_CONTRIBUTORS: SingleNamedItemHook[ContentContributor] = SingleNamedItemHook()
