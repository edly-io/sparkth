"""Compose's planner: hands each message to the agent suited for it, answers small talk itself, or refuses.

Each enabled agent becomes one of the planner's tools. Calling it runs that agent's own graph on
the conversation and ends the planner's run with the agent's reply, so nothing the planner writes
after a hand-off reaches the author. Hand-offs and refusals act on no system, so the audit
callback skips them; the tools an agent calls are still audited.
"""

from sparkth.plugins.compose.planner.graph import build_planner, render_planner_prompt
from sparkth.plugins.compose.planner.tools import agent_input
from sparkth.plugins.compose.planner.types import AgentGraph

__all__ = ["AgentGraph", "agent_input", "build_planner", "render_planner_prompt"]
