"""Audit trail internals: the system-of-record write path for audit events.

Application code and plugins import the public surface from
:mod:`app.lib.audit`, never from this package directly.
"""
