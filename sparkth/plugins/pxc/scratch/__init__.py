"""Run an activity's actions against a throwaway store, outside any launch.

A run is a child process, so one that never ends can be killed: ``python -m
sparkth.plugins.pxc.scratch`` runs an agent's own steps, and ``python -m
sparkth.plugins.pxc.scratch.smoke`` runs the build's smoke test. Each names every step on a line of
stdout starting with ``PXC_STEP_PREFIX`` before running it, so a step that never ends can be named.
"""
