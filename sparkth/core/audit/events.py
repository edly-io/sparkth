"""Self-describing audit event types.

An audit event type is a frozen dataclass subclassing :class:`BaseAuditEvent`:
the class carries its own identity (``event_type``, ``fail_open``) as
ClassVars and only grouped envelope fields, so :func:`sparkth.lib.audit.record_event`
takes the session and one event object instead of a flat argument list.

Event classes are registered on the module-level :data:`AUDIT_EVENTS` hook
(mirroring the permissions hooks and the analytics schema registry): the
taxonomy stays explicit, a duplicate event type collides loudly, and plugins
can register their own event classes without editing core. The grouped
envelope value objects live in :mod:`sparkth.core.audit.types`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, TypeVar

from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError
from sparkth.core.audit.types import AuditActor, AuditChange, AuditModelInfo, AuditTarget, AuditToolCall
from sparkth.lib.hooks import KeyedClassHook


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseAuditEvent:
    """One audit event, ready to be recorded.

    Subclass per event type, set ``event_type`` (``category.action``), and
    register the class on :data:`AUDIT_EVENTS`. ``fail_open`` opts a
    read-class event type out of the default fail-closed write semantics:
    mutating and AI event types must keep the default ``False``.

    The base carries only the fields every category has. ``actor`` and
    ``occurred_at`` are optional because the recorder resolves them (context
    actor or anonymous; current time). ``target`` is what the action acted
    on; for a failed login it carries the *claimed* username as untrusted
    evidence. Mutation snapshots live on :class:`MutationAuditEvent` and AI
    provenance on :class:`AIActionAuditEvent`, so a category never exposes
    fields it cannot have.
    """

    event_type: ClassVar[str]
    fail_open: ClassVar[bool] = False

    outcome: AuditOutcome
    actor: AuditActor | None = None
    error_detail: str | None = None
    occurred_at: datetime | None = None
    target: AuditTarget | None = None

    @property
    def category(self) -> str:
        return self.event_type.partition(".")[0]

    @property
    def action(self) -> str:
        return self.event_type.partition(".")[2]


@dataclass(frozen=True, slots=True, kw_only=True)
class MutationAuditEvent(BaseAuditEvent):
    """Base for events that change stored state.

    ``change`` carries the redactable before/after snapshots (the NIST AU-3
    "what effect" field); a denied or failed mutation may have none.
    """

    change: AuditChange | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AIActionAuditEvent(MutationAuditEvent):
    """Base for AI-driven actions (tool calls, generations).

    Extends the mutation base because AI actions often mutate; read-only AI
    actions leave ``change`` unset. ``purpose`` is reserved for FERPA
    disclosure logging.
    """

    tool: AuditToolCall | None = None
    model: AuditModelInfo | None = None
    purpose: str | None = None


E = TypeVar("E", bound=BaseAuditEvent)


class AuditEventTypeHook(KeyedClassHook[BaseAuditEvent]):
    """Hook mapping event types to their event classes.

    A :class:`sparkth.lib.hooks.KeyedClassHook` keyed by ``event_type``, adding
    the ``category.action`` format check and the audit exception types.
    """

    def register(self, event_cls: type[E]) -> type[E]:
        """Register ``event_cls`` under its event type; usable as a decorator.

        Raises:
            ValueError: ``event_type`` is not ``category.action``.
            DuplicateAuditEventTypeError: A different class already claims
                the event type.
        """
        event_type = event_cls.event_type
        category, _, action = event_type.partition(".")
        if not category or not action:
            raise ValueError(f"Audit event type must be 'category.action', got '{event_type}'")
        if not self.add_class(event_type, event_cls):
            raise DuplicateAuditEventTypeError(event_type)
        return event_cls

    def resolve(self, event_type: str) -> type[BaseAuditEvent]:
        """Return the class registered for ``event_type``.

        Raises:
            UnknownAuditEventTypeError: No class is registered.
        """
        event_cls = self.get(event_type)
        if event_cls is None:
            raise UnknownAuditEventTypeError(event_type)
        return event_cls

    def require(self, event_cls: type[BaseAuditEvent]) -> None:
        """Assert ``event_cls`` is the registered class for its event type.

        Raises:
            UnknownAuditEventTypeError: The class (or its event type) is not
                registered; recording it is a programming error.
        """
        if self.get(event_cls.event_type) is not event_cls:
            raise UnknownAuditEventTypeError(event_cls.event_type)


AUDIT_EVENTS: AuditEventTypeHook = AuditEventTypeHook()


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LoginAuditEvent(BaseAuditEvent):
    """An authentication attempt: success, bad credentials, or denied."""

    event_type: ClassVar[str] = "auth.login"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class PermissionDeniedAuditEvent(BaseAuditEvent):
    """A ``Permission.require*`` dependency refused a request with 403.

    ``target`` is the permission checked; ``error_detail`` names the scope
    (and the scope object id from the route's path, when the scope has one).
    The actor is the authenticated caller bound by ``get_current_user``.
    """

    event_type: ClassVar[str] = "permission.denied"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RegisteredAuditEvent(MutationAuditEvent):
    """An account was created: password registration, Google sign-up, or the CLI.

    ``target`` is the new user and ``change.new`` carries only the ``method``
    (``password``, ``google`` or ``cli``). A self-registration has the new
    user as actor too, with the username on the actor label, which a GDPR
    erasure can blank; a sealed payload never carries the actor's own
    identity. An account created by ``users create-user`` has the CLI system
    actor instead.
    """

    event_type: ClassVar[str] = "auth.registered"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class EmailVerifiedAuditEvent(BaseAuditEvent):
    """An email verification attempt: the token was redeemed, or rejected.

    A rejection is anonymous (nobody proved who they are) and never records
    the token itself, only why it was rejected.
    """

    event_type: ClassVar[str] = "auth.email_verified"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class PasswordResetAuditEvent(MutationAuditEvent):
    """A user's password was replaced by an operator (``users reset-password``).

    ``target`` is the user; ``change.new`` carries only the ``method``
    (``cli``), never the password or its hash.
    """

    event_type: ClassVar[str] = "auth.password_reset"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GoogleLinkedAuditEvent(MutationAuditEvent):
    """A Google identity was attached to an existing account: a new way to
    log in, so a credential-lifecycle event."""

    event_type: ClassVar[str] = "auth.google_linked"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class WhitelistEntryAddedAuditEvent(MutationAuditEvent):
    """An email or domain was added to the registration allowlist.

    ``target`` is the entry; ``change.new`` carries the normalized ``value``
    and its ``entry_type`` (``email`` or ``domain``): the value is the
    evidence of who was allowed to register.
    """

    event_type: ClassVar[str] = "whitelist.entry_added"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class WhitelistEntryRemovedAuditEvent(MutationAuditEvent):
    """An allowlist entry was removed. ``change.old`` carries its ``value``
    and ``entry_type``."""

    event_type: ClassVar[str] = "whitelist.entry_removed"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LLMConfigCreatedAuditEvent(MutationAuditEvent):
    """A stored LLM API key was created. ``change.new`` never carries key
    material, only name, provider, and model."""

    event_type: ClassVar[str] = "llm_config.created"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LLMConfigUpdatedAuditEvent(MutationAuditEvent):
    """An LLM config's name, model, or active flag changed."""

    event_type: ClassVar[str] = "llm_config.updated"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LLMConfigKeyRotatedAuditEvent(MutationAuditEvent):
    """The stored API key was replaced; the snapshots hold the masked keys."""

    event_type: ClassVar[str] = "llm_config.key_rotated"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LLMConfigDeletedAuditEvent(MutationAuditEvent):
    """An LLM config was soft-deleted."""

    event_type: ClassVar[str] = "llm_config.deleted"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LLMConfigKeyReadAuditEvent(BaseAuditEvent):
    """A stored API key was decrypted for use: the credential access trail.

    Recorded on every :meth:`LLMConfigService.resolve`, cache hit or not, in the
    caller's transaction.
    """

    event_type: ClassVar[str] = "llm_config.key_read"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class UserPluginConfigCreatedAuditEvent(MutationAuditEvent):
    """A user configured a plugin for the first time.

    Plugin configs are mostly credentials under plugin-specific key names
    that key-based redaction cannot know, so the snapshots carry the plugin
    name and the sorted config *keys*, never a value.
    """

    event_type: ClassVar[str] = "user_plugin.config_created"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class UserPluginConfigUpdatedAuditEvent(MutationAuditEvent):
    """A user's plugin configuration changed (keys only, see above)."""

    event_type: ClassVar[str] = "user_plugin.config_updated"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class UserPluginEnabledChangedAuditEvent(MutationAuditEvent):
    """A user enabled or disabled a plugin for themselves."""

    event_type: ClassVar[str] = "user_plugin.enabled_changed"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RoleCreatedAuditEvent(MutationAuditEvent):
    """A role was created; ``change.new`` carries its name and description."""

    event_type: ClassVar[str] = "role.created"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RoleUpdatedAuditEvent(MutationAuditEvent):
    """A role's name or description changed."""

    event_type: ClassVar[str] = "role.updated"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RoleDeletedAuditEvent(MutationAuditEvent):
    """A role was deleted along with its grants; ``change.old`` carries its name and description."""

    event_type: ClassVar[str] = "role.deleted"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RolePermissionGrantedAuditEvent(MutationAuditEvent):
    """A permission was granted to a role that did not hold it."""

    event_type: ClassVar[str] = "role.permission_granted"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RolePermissionRevokedAuditEvent(MutationAuditEvent):
    """A permission a role held was revoked from it."""

    event_type: ClassVar[str] = "role.permission_revoked"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RoleAssignedAuditEvent(MutationAuditEvent):
    """A role was assigned to a user at a scope.

    ``target`` is the user; the snapshot carries the role name, the scope kind, and
    the scope object id. Recorded only when a new assignment was created.
    """

    event_type: ClassVar[str] = "role.assigned"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RoleUnassignedAuditEvent(MutationAuditEvent):
    """A user's active assignment of a role at a scope was revoked."""

    event_type: ClassVar[str] = "role.unassigned"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupCreatedAuditEvent(MutationAuditEvent):
    """A group was created; ``change.new`` carries its name and description."""

    event_type: ClassVar[str] = "group.created"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupUpdatedAuditEvent(MutationAuditEvent):
    """A group's name or description changed."""

    event_type: ClassVar[str] = "group.updated"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupDeletedAuditEvent(MutationAuditEvent):
    """A group was deleted along with its membership and assignment history."""

    event_type: ClassVar[str] = "group.deleted"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupMemberAddedAuditEvent(MutationAuditEvent):
    """A user joined a group; the snapshot carries the ``user_id``."""

    event_type: ClassVar[str] = "group.member_added"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupMemberRemovedAuditEvent(MutationAuditEvent):
    """A user's active membership in a group was removed."""

    event_type: ClassVar[str] = "group.member_removed"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupRoleAssignedAuditEvent(MutationAuditEvent):
    """A role was assigned to a group at a scope (snapshot shaped like ``role.assigned``)."""

    event_type: ClassVar[str] = "group.role_assigned"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class GroupRoleRevokedAuditEvent(MutationAuditEvent):
    """A group's active assignment of a role at a scope was revoked."""

    event_type: ClassVar[str] = "group.role_revoked"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class ToolInvokedAuditEvent(AIActionAuditEvent):
    """An AI tool call accepted for execution.

    Committed *before* the handler runs (ADR-0002 fail-closed semantics): if
    this event cannot be written, the tool call is refused. ``target`` carries
    the generated invocation id shared with the outcome event.
    """

    event_type: ClassVar[str] = "tool.invoked"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCompletedAuditEvent(AIActionAuditEvent):
    """An AI tool call whose handler returned normally."""

    event_type: ClassVar[str] = "tool.completed"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class ToolFailedAuditEvent(AIActionAuditEvent):
    """An AI tool call whose handler raised, or that failed before reaching
    a handler (protocol-level: unknown tool, input validation)."""

    event_type: ClassVar[str] = "tool.failed"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RAGDocumentIngestedAuditEvent(MutationAuditEvent):
    """A document's content entered the RAG corpus, or failed to.

    Recorded by :func:`sparkth.lib.rag.ingest_document` for every attempt:
    ``target`` is the document, ``change.new`` carries the filename and chunk
    counts on success, and a failed extraction records outcome ``failure``
    with the scrubbed error instead.
    """

    event_type: ClassVar[str] = "rag.document_ingested"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RAGDocumentDeletedAuditEvent(MutationAuditEvent):
    """A document was removed from the retrieval corpus (soft-deleted).

    Recorded by :func:`sparkth.lib.documents.soft_delete_document` in the
    caller's transaction; ``change.old`` snapshots the document name.
    """

    event_type: ClassVar[str] = "rag.document_deleted"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RAGChunksPurgedAuditEvent(MutationAuditEvent):
    """A cleanup run hard-deleted the chunks of soft-deleted documents.

    The system-actor evidence that content removal actually happened:
    ``change.old`` lists the processed document ids and the purged chunk
    count. One event per cleanup run that found work.
    """

    event_type: ClassVar[str] = "rag.chunks_purged"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class RetentionPurgedAuditEvent(MutationAuditEvent):
    """A retention run deleted the audit events of one category past their retention.

    Recorded by :func:`sparkth.lib.audit.purge_expired_events`, one per category
    that lost rows (``"*"`` for the default policy covering every category
    without an override), committed atomically with the deletion. ``change.old``
    carries the category, the retention window applied, and the row count: the
    evidence that a gap in the trail is policy, not tampering.
    """

    event_type: ClassVar[str] = "audit.retention_purged"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class ActorErasedAuditEvent(MutationAuditEvent):
    """A GDPR erasure blanked one user's personal data across the trail.

    Recorded by :func:`sparkth.lib.audit.erase_actor` in the erasure's own
    transaction; ``target`` is the user (by pseudonymous id, the one identifier
    that survives) and ``change.old`` the number of rows touched.
    """

    event_type: ClassVar[str] = "audit.actor_erased"
