"""Constants for Compose agents."""

import re
from typing import Final

# The name of the tool Compose's planner refuses a message with.
REFUSE_TOOL_NAME: Final = "refuse"

# The name of Compose's planner, which hands each message to an agent.
PLANNER_AGENT_NAME: Final = "compose"

# The name of Compose's operator, which runs operations such as publishing a course.
OPERATOR_AGENT_NAME: Final = "operator"

# Names Compose keeps for itself.
RESERVED_AGENT_NAMES: Final = frozenset({PLANNER_AGENT_NAME, OPERATOR_AGENT_NAME, REFUSE_TOOL_NAME})

# An agent's name is the tool name Compose calls it by.
AGENT_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")
