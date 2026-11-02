"""Chat's own capability: designing, building and publishing courses."""

from sparkth.lib.compose.hooks import ChatCapability
from sparkth.plugins.compose.constants import COURSE_DESIGN_PROMPT, COURSE_DESIGN_SCOPE, COURSE_DESIGN_TITLE

COURSE_DESIGN = ChatCapability(COURSE_DESIGN_TITLE, COURSE_DESIGN_SCOPE, COURSE_DESIGN_PROMPT)
