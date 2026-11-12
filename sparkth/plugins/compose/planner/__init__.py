"""Compose's planner: hands each message to the agent suited for it, runs operations, answers small
talk itself, or refuses.

Each enabled agent becomes one of the planner's tools. Calling it runs that agent's own graph on
the conversation and ends the planner's run with the agent's reply, so nothing the planner writes
after a hand-off reaches the author. The operator tool runs operations, such as publishing a
course, and returns what they did to the planner. Hand-offs, operations and refusals are skipped
by the audit callback; the tools an agent or the operator calls are still audited.
"""

from sparkth.plugins.compose.planner.graph import build_planner, render_planner_prompt
from sparkth.plugins.compose.planner.tools import agent_input
from sparkth.plugins.compose.planner.types import AgentGraph, TurnRouting

__all__ = ["AgentGraph", "TurnRouting", "agent_input", "build_planner", "render_planner_prompt"]
