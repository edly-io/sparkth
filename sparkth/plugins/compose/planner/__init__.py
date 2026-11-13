"""Compose's planner: hands each message to the agent suited for it, runs operations, answers small
talk itself, or refuses.

Each enabled agent becomes one of the planner's tools. Calling it runs that agent's own graph on
the conversation, and the author reads the agent's reply as it is written. What a step returns goes
back to the planner, which runs the next part the author asked for, another agent's or an
operation, with every step reading what the earlier ones wrote, or ends the turn. The operator
tool runs operations, such as publishing a course; the author reads what they did from the planner.
Hand-offs, operations and refusals are skipped by the audit callback; the tools an agent or the
operator calls are still audited.
"""

from sparkth.plugins.compose.planner.graph import build_planner, render_planner_prompt
from sparkth.plugins.compose.planner.tools import agent_input
from sparkth.plugins.compose.planner.types import AgentGraph, TurnRouting

__all__ = ["AgentGraph", "TurnRouting", "agent_input", "build_planner", "render_planner_prompt"]
