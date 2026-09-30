# Audit events

An audit event is an append-only row in `audit_events` recording who did what, when, from where
and with what effect. It is evidence, not measurement: a single missing row is a defect. This
guide covers the judgement around one: whether it belongs in audit at all, which base class it
extends, what its snapshots may carry, which transaction it writes in, and how to test it.

The API itself (`record_event`, `record_event_now`, the event classes, the context helpers) is
documented in the docstrings under `sparkth/lib/audit/`, rendered by `make docs`. Import from
`sparkth.lib.audit.*`, never from `sparkth.core.audit.*`.

An event type is a permanent contract. Once rows exist, the retention policy, erasure, reviewers
and any export depend on its `category.action`, its target type and the keys of its snapshots,
and the rows cannot be rewritten to match a rename: the table rejects `UPDATE`. Adding, renaming,
splitting, merging or dropping one is a deliberate decision, not a detail of the change that
motivated it.

## Audit or analytics?

The two systems fail in opposite directions on purpose. The comparison table is in the
[analytics events guide](analytics-events.md#analytics-or-audit-they-fail-differently-on-purpose).
In short:

- **Audit** is fail-closed. The record is written before, or atomically with, the action. If it
  cannot be written, the action does not happen.
- **Analytics** is fail-open. It is emitted after the response and its counts are lower bounds.

Record it in audit when losing one row is unacceptable: authentication, credentials, account and
permission changes, plugin configuration, content entering or leaving the corpus, AI tool
executions, and maintenance of the trail itself. If the value is in the rate, not the row, it is
analytics. Something can be both (login is), in which case it gets one event in each system and
neither is derived from the other.

## Before adding one

- **Is it already recorded?** Every AI tool execution already records `tool.invoked` plus
  `tool.completed` or `tool.failed` on every surface (see
  [Tool executions are covered already](#tool-executions-are-covered-already)). A tool that
  mutates something does not need its own mutation event unless the mutation also happens outside
  the tool.
- **Who is the actor?** A user, the system, or an anonymous caller. If you cannot say, the seam is
  wrong.
- **What is the target?** The entity acted on, as `AuditTarget(type, id)`. Pick a `type` that is
  stable and already used where one exists (`document`, `llm_config`, `user_plugin`, `username`).
- **Which outcomes exist?** `success`, `failure`, `denied`. A refusal the system decided on is
  `denied`, an error is `failure`. Record the negative paths, not only the happy one: a trail
  with only successes cannot answer "who tried".
- **What does it cost?** One row per occurrence, kept for the category's retention window
  (`AUDIT_RETENTION_DAYS`, overridable per category via `AUDIT_RETENTION_OVERRIDES`). An event on
  a hot path (every chat turn) is real volume; say so.

## Declaring an event

An event type is a frozen, slotted, keyword-only dataclass registered on the `AUDIT_EVENTS` hook.
Pick the base by what the action is:

| Base | For | Adds |
|---|---|---|
| `BaseAuditEvent` | An action that changes nothing stored: login, key read, verification | `outcome`, `actor`, `target`, `error_detail`, `occurred_at` |
| `MutationAuditEvent` | A change to stored state | `change: AuditChange(old=..., new=...)` |
| `AIActionAuditEvent` | An action driven by a model | `tool`, `model`, `purpose` |

```python
from dataclasses import dataclass
from typing import ClassVar

from sparkth.lib.audit.events import MutationAuditEvent
from sparkth.lib.audit.hooks import AUDIT_EVENTS


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class WidgetDeletedAuditEvent(MutationAuditEvent):
    """A widget was deleted. ``change.old`` carries its name."""

    event_type: ClassVar[str] = "widget.deleted"
```

- `event_type` must be `category.action`; registration raises `ValueError` otherwise, and a second
  class claiming the same type raises `DuplicateAuditEventTypeError`.
- The **category** is the retention unit: `AUDIT_RETENTION_OVERRIDES` is keyed by it. Put events
  that must be kept for the same length of time in the same category, and give a plugin's events
  a category of its own so an override for one plugin never reaches another.
- Recording an unregistered class raises `UnknownAuditEventTypeError`. Make sure the module that
  declares the class is imported at startup (core events register when
  `sparkth.core.audit.events` is first imported, via `sparkth.lib.audit`; a plugin imports its
  events module from its `__init__`).
- Leave `fail_open` at `False`. It exists for read-class events where the caller may choose to log
  and continue; mutating and AI events must stay fail-closed. Even when it is `True` the recorder
  still raises, and the call site owns the decision.
- The actor taxonomy is closed: `UserActor`, `SystemActor`, `AnonymousActor`. Never add a kind.

## What a snapshot may carry

`AuditChange.old` / `new`, `AuditToolCall.args`, `target.id` and `error_detail` are persisted and
sealed into `canonical_bytes`. They cannot be edited afterwards, so what goes in is final.

**Redaction is by exact key name, and only a backstop.** `redact` replaces the value of any key in
`SECRET_KEYS` (`password`, `token`, `api_key`, `auth`, ...) at any depth. It cannot recognise
`lms_password`, `signing_secret` or a key a plugin invented. Design the snapshot so it would be
safe with redaction switched off:

- **Never key material.** Record a masked form (`masked_key`) or nothing.
- **Plugin or other free-form configs: key names only.** `{"plugin": name, "keys": sorted(config)}`
  is the shape to copy (`PluginService._config_snapshot`).
- **Never the actor's own identity in a snapshot.** The actor's username rides on `actor_label`,
  which sits outside the seal so a GDPR erasure can blank it. A username copied into `change.new`
  is sealed and can never be erased. (`auth.registered` records only the `method` for this
  reason.)
- **Never content.** Message bodies, course content, prompts, model output. Record the name or id
  of the thing and its shape (chunk counts, sizes), not the thing.
- **Names identifying the target are fine**, unlike analytics. A deleted document's name is the
  evidence of *what* was deleted. Keep it to the identifying field, not the whole row.
- **Unverified identity goes on the target, never the actor.** A failed login records the typed
  username as `AuditTarget(type="username", id=...)` with an `AnonymousActor`.

**`error_detail` is free text, so it is the riskiest field.** Use `scrub_error_detail(exc)`, which
strips Pydantic inputs, masks secret-keyed assignments and bounds the length, or a fixed string
the system authored (`"incorrect password"`). Never `str(exc)`.

## Actor, source and time come from the context

Do not pass them unless the context is wrong for this event.

- **Actor.** Authenticated requests bind the user through `get_current_user`; an event recorded
  after that is attributed automatically. Pass `actor=` only to override it: `AnonymousActor()`
  for an unauthenticated attempt, `SystemActor(label=...)` for a job.
- **Source and request origin.** The ASGI middleware installs a `REST` (or `MCP`) request context
  per request. Code with no request (CLI commands, scheduled jobs, detached tasks) installs its own
  with `audit_context(AuditSystemContext(source=..., actor=SystemActor(...)))`, or it is recorded
  as an anonymous `system` event. AI seams wrap tool execution in `ai_audit_context(source, model)`
  so the chat or RAG surface and the model reach the row.
- **Time.** `occurred_at` defaults to the moment the event is built. Recording is synchronous with
  the action, so the default is normally right; set it only when recording something that
  happened earlier.

## Choosing the transaction

This is where audit correctness lives.

| Situation | Use |
|---|---|
| The action is a write in a session you hold | `record_event(session, event)` in that session, before the commit |
| The event must survive the request failing or rolling back (a failed login, a failed ingestion) | `record_event_now(event)`, its own committed transaction |
| The action must not start unless the record exists (a tool call) | `record_event_now` *before* the action (the `tool.invoked` pattern) |
| A read that decrypts or discloses something | `record_event` in the caller's session if the caller commits right after, otherwise `record_event_now` |

`record_event` only flushes: the row commits or rolls back with the mutation, so there is never a
mutation without its record or a record of a mutation that did not happen. That is why it takes
the caller's session. It also costs nothing extra; `record_event_now` opens a second connection,
which on a hot path competes with the request for the pool.

A denied or failed attempt is usually followed by an `HTTPException` or a re-raise that rolls the
request's session back. Record those with `record_event_now`, or the evidence rolls back with the
request.

## Never swallow an audit write

Fail-closed means the error from `record_event` / `record_event_now` propagates and fails the
action. So:

- No `try`/`except` around a record call that turns its failure into a success.
- A broad handler that converts errors into user- or model-visible messages must let the audit
  error through. `AuditCaptureError` exists so the chat tool executor can re-raise an audit
  outage instead of reporting it to the model as a tool error.
- When recording a failure from inside an `except` block, record, then re-raise the original
  (`sparkth/rag/ingestion/__init__.py` is the shape). If the record itself fails, that error
  replaces the original, which is the correct, loud outcome.

This is the opposite of the analytics rule, deliberately: analytics must not affect the request,
audit must.

## Tool executions are covered already

Do not hand-write audit code in a tool. Three seams record every execution:

- `Tool` wraps its handler with `audited_tool` at construction, covering the MCP server and the
  chat registry.
- `AuditToolCallbackHandler`, active process-wide, covers any tool LangChain runs (the RAG agent).
  A tool already audited at the handler level carries `AUDIT_AT_HANDLER_TAG` so it is not recorded
  twice.
- The FastMCP `ToolCallAuditMiddleware` records protocol-level failures that never reach a
  handler (unknown tool, invalid input).

`tests/audit/test_capture_completeness.py` pins the set of modules allowed to construct executable
tools. A new execution path that fails it needs one of the seams above, not an exemption.

## Maintenance is the only way past append-only

Database triggers reject `UPDATE`, `DELETE` and `TRUNCATE` on `audit_events`. Corrections are new
events. The two sanctioned exceptions, `purge_expired_events` (retention, `python -m sparkth.cli.main audit purge`)
and `erase_actor` (GDPR, `audit erase-user <id>`), unlock the table only for their own
transaction and record their own event (`audit.retention_purged`, `audit.actor_erased`). Do not
add a third without the same properties.

## Tests

Follow TDD, and assert on rows that actually landed, using the `audit_events` fixture from
`sparkth/lib/testing.py`:

- **Drive the real seam** (the endpoint or service method), then read the rows. Asserting a
  mocked `record_event` was called proves nothing about the row.
- **Assert the envelope**: `(category, action)`, `outcome`, `actor_type` / `actor_id`,
  `target_type` / `target_id`, and the snapshot keys.
- **Assert what must be absent.** Search `canonical_bytes` for the secret or content that must not
  be there (`tests/llm/test_service_audit.py`, `_assert_no_key_material`).
- **Cover every outcome** the event declares, not only `success`.
- **Prove it is fail-closed.** Make the record call raise (`monkeypatch` it to raise
  `SQLAlchemyError`) and assert the action did not happen or the request failed
  (`tests/api/v1/test_auth_audit.py`, `test_login_is_fail_closed_when_audit_write_fails`).
- **Prove the transaction choice.** For `record_event`, roll back and assert the row is gone with
  the mutation. For `record_event_now`, fail the request and assert the row survives.
- **Prove the test has bite.** Delete the record call and confirm the test fails.

## Migrations

New event types are rows in the existing `audit_events` table. **No migration.** A new column on
the table is a schema change and follows the `database-migrations` skill; decide first whether it belongs inside the seal (`canonical_bytes`) or must stay erasable
outside it.
