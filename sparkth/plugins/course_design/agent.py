"""The course design agent: designs courses, lessons and written assessments in Compose."""

from pathlib import Path

from sparkth.lib.compose.hooks import Agent

_ASSETS = Path(__file__).parent / "assets"

COURSE_DESIGN = Agent(
    "course_design",
    title="Course design",
    description=(_ASSETS / "course_design_description.txt").read_text(encoding="utf-8").strip(),
    prompt=(_ASSETS / "course_design_prompt.txt").read_text(encoding="utf-8").strip(),
)
