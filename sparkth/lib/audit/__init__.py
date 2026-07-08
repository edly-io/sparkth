"""Audit trail public API: the curated surface for recording audit events.

The write path lives here (:func:`record_event`, :func:`record_event_now`);
the rest of the surface is split by concern into submodules:
:mod:`app.lib.audit.events` (event classes, value objects, outcomes),
:mod:`app.lib.audit.context` (actors, contexts, context helpers),
:mod:`app.lib.audit.hooks` (the ``AUDIT_EVENTS`` hook), and
:mod:`app.lib.audit.exceptions`. Never import from ``app.core.audit.*``
directly; implementation lives in :mod:`app.core.audit`.

The audit trail is the append-only system of record for who did what, when,
and with what effect. It is deliberately *not* the analytics pipeline:
analytics (:mod:`app.lib.analytics`) is best-effort and droppable, audit is
fail-closed, meaning an event that cannot be written fails the mutating or AI
action it records.
"""

from sparkth.core.audit.recorder import record_event, record_event_now

__all__ = [
    "record_event",
    "record_event_now",
]
