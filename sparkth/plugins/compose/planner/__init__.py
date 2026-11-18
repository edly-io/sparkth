"""Compose's planner: hands each message to the agent suited for it, runs operations, answers small
talk itself, or refuses.

A step is work the planner gives to one enabled agent, or to the operator for an operation. What
the step returns goes back to the planner, which runs the next step or ends the turn.
"""

from sparkth.plugins.compose.planner.graph import build_planner, render_planner_prompt
from sparkth.plugins.compose.planner.tools import agent_input
from sparkth.plugins.compose.planner.types import AgentGraph, OpenPlan, PlannedStep, TurnRouting

__all__ = [
    "AgentGraph",
    "OpenPlan",
    "PlannedStep",
    "TurnRouting",
    "agent_input",
    "build_planner",
    "render_planner_prompt",
]
