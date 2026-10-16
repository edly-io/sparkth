"""Chat's own job: designing, building and publishing courses."""

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import (
    COURSE_DESIGN_LABEL,
    COURSE_DESIGN_SCOPE,
    COURSE_DESIGN_SYSTEM_PROMPT,
    COURSE_DESIGN_TITLE,
    DEFAULT_RESPONSIBILITY,
)

COURSE_DESIGN = ChatResponsibility(
    DEFAULT_RESPONSIBILITY,
    COURSE_DESIGN_LABEL,
    COURSE_DESIGN_TITLE,
    COURSE_DESIGN_SCOPE,
    COURSE_DESIGN_SYSTEM_PROMPT,
    frozenset(),
)
