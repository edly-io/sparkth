"""The PXC agent: builds and updates interactive activities in Compose."""

from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.pxc.constants import (
    PXC_ACTIVITY_BUILDER_DESCRIPTION,
    PXC_ACTIVITY_BUILDER_PROMPT,
    PXC_ACTIVITY_BUILDER_TITLE,
)
from sparkth.plugins.pxc.tools import PXC_TOOLS

PXC_ACTIVITY_BUILDER = Agent(
    "pxc_activities",
    PXC_ACTIVITY_BUILDER_TITLE,
    PXC_ACTIVITY_BUILDER_DESCRIPTION,
    PXC_ACTIVITY_BUILDER_PROMPT,
    tools=tuple(PXC_TOOLS),
)
