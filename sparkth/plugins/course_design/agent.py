"""The course design agent: designs courses, lessons and written assessments in Compose."""

from sparkth.lib.assets import read_asset
from sparkth.lib.compose.hooks import Agent

COURSE_DESIGN = Agent(
    "course_design",
    title="Course design",
    description=read_asset(__file__, "course_design_description.txt"),
    prompt=read_asset(__file__, "course_design_prompt.txt"),
)
