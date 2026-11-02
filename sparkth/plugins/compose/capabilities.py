"""Compose's own agent: designing, building and publishing courses."""

from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import COURSE_DESIGN_PROMPT, COURSE_DESIGN_SCOPE, COURSE_DESIGN_TITLE

COURSE_DESIGN = Agent(COURSE_DESIGN_TITLE, COURSE_DESIGN_SCOPE, COURSE_DESIGN_PROMPT)
