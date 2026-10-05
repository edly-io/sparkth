"""The audit context CLI commands run in, so their rows are attributed to the CLI."""

from collections.abc import Iterator
from contextlib import contextmanager

from sparkth.lib.audit.context import AuditContext, AuditSource, AuditSystemContext, SystemActor, audit_context


@contextmanager
def cli_audit_context() -> Iterator[AuditContext]:
    """Attribute audit events recorded in the enclosed block to the CLI system actor."""
    with audit_context(AuditSystemContext(source=AuditSource.CLI, actor=SystemActor(label="cli"))) as context:
        yield context
