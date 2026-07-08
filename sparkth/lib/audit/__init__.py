"""Audit trail public API: the curated surface for recording audit events.

The write path lives here (:func:`record_event`, :func:`record_event_now`);
the rest of the surface is split by concern into submodules:
:mod:`sparkth.lib.audit.events` (event classes, value objects, outcomes),
:mod:`sparkth.lib.audit.context` (actors, contexts, context helpers),
:mod:`sparkth.lib.audit.hooks` (the ``AUDIT_EVENTS`` hook), and
:mod:`sparkth.lib.audit.exceptions`. Never import from ``sparkth.core.audit.*``
directly; implementation lives in :mod:`sparkth.core.audit`.

The audit trail is the append-only system of record for who did what, when,
and with what effect. It is deliberately *not* the analytics pipeline:
analytics (:mod:`sparkth.lib.analytics`) is best-effort and droppable, audit is
fail-closed, meaning an event that cannot be written fails the mutating or AI
action it records.
"""

from sparkth.core.audit.recorder import record_event, record_event_now

__all__ = [
    "record_event",
    "record_event_now",
]
