"""Constants for Compose agents."""

import re
from typing import Final

# Names Compose keeps for itself.
RESERVED_AGENT_NAMES: Final = frozenset({"compose", "operator"})

# An agent's name is the tool name Compose calls it by.
AGENT_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")
