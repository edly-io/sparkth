"""Constants for Compose agents."""

import re
from typing import Final

# The name of the tool Compose's planner refuses a message with.
REFUSE_TOOL_NAME: Final = "refuse"

# The name of Compose's planner, which hands each message to an agent.
PLANNER_NAME: Final = "compose"

# The planner's tool that runs operations, such as publishing a course.
OPERATOR_TOOL_NAME: Final = "operator"

# Names Compose keeps for itself.
RESERVED_AGENT_NAMES: Final = frozenset({PLANNER_NAME, OPERATOR_TOOL_NAME, REFUSE_TOOL_NAME})

# An agent's name is the tool name Compose calls it by.
AGENT_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")
