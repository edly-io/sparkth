"""Chat's own capability: designing, building and publishing courses."""

from sparkth.lib.chat.hooks import ChatCapability
from sparkth.plugins.chat.constants import COURSE_DESIGN_SCOPE, COURSE_DESIGN_SYSTEM_PROMPT, COURSE_DESIGN_TITLE

COURSE_DESIGN = ChatCapability(COURSE_DESIGN_TITLE, COURSE_DESIGN_SCOPE, COURSE_DESIGN_SYSTEM_PROMPT)
