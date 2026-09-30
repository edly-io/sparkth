---
name: audit-events
description: Use when adding, changing or removing a Sparkth audit event: recording an authentication, credential, account, permission, plugin-config, corpus or AI action in the audit trail, filling a gap where a security-relevant action leaves no record, changing an existing audit event's snapshot, target, outcome or transaction, or touching sparkth/lib/audit. Also when deciding whether something belongs in audit or analytics.
---

# Audit Events

**You propose events. The developer decides.** This skill is how to make a proposal worth
deciding on. Everything about the events themselves (audit vs analytics, base class, snapshot
safety, transaction choice, fail-closed handling, the testing standard) is in
[`docs/guides/audit-events.md`](../../../docs/guides/audit-events.md).

**Read that guide before writing any code.** Do not work from this file alone.

## The developer owns the vocabulary

An audit event type is a permanent contract, and harder to undo than an analytics one: the table
rejects `UPDATE`, so rows written under a wrong name, target type or snapshot shape stay that way
until retention deletes them. Retention overrides, GDPR erasure and any export key off the
category and fields. That decision is not yours.

Never add, rename, split, merge or drop an event on your own judgement. Put a proposal to the
developer: the `category.action`, the base class, the actor, the target type, every outcome, the
snapshot keys, the transaction (`record_event` or `record_event_now`), and what it costs. Then
wait for an answer.

**A proposal already written down is not a decision.** An event set spelled out in an issue (even
one the developer filed themselves) is still a proposal until they say to build it. Ask once,
naming anything the issue left open, and take the answer as the decision. Do not treat your own
earlier draft as an approval.

**Red flags: stop and ask:**

- You are about to write `@AUDIT_EVENTS.register` on a class nobody named
- You are choosing between one event with an outcome and two separate events
- You are adding a key to an existing event's snapshot
- You are picking a new category (it is the retention unit)
- You are setting `fail_open = True`
- You are adding audit code inside a tool handler (tool executions are already recorded)
- You are inferring the event set from an issue description rather than confirming it

**All of these mean: propose, then wait.** Recommending is your job; a proposal with no
recommendation is unhelpful. Deciding is not.

| Rationalization | Reality |
|---|---|
| "The issue says what's needed" | An issue states a problem. The vocabulary is a separate decision. |
| "It's security-relevant, so obviously audit it" | Say what it answers and what it costs. Then let them choose. |
| "I'll add it and they can rename it later" | Rows cannot be updated. Old rows keep the old name until retention. |
| "It's just one more snapshot key" | Every key is sealed into `canonical_bytes` and can never be erased. |
| "This tool mutates, so it needs its own event" | `tool.invoked` / `tool.completed` already record it. Propose only if the mutation also happens outside the tool. |

## What the proposal must answer

Taken from the guide's *Before adding one*; answer all of them in the proposal itself:

- **Is it already recorded?** Check the event list in `sparkth/lib/audit/events.py` and the tool
  execution seams. If it is covered, propose nothing.
- **Who is the actor, and what is the target?**
- **Which outcomes exist?** `success`, `failure`, `denied`. Negative paths are the point.
- **Which transaction?** Joins the mutation's session, or must survive a rollback.
- **What does it cost?** Say the volume out loud, and the retention it inherits.

## Three rules you must not violate while building

All are explained in the guide; none is a judgement call.

- **Snapshots must be safe with redaction switched off.** Redaction matches exact key names only.
  Never key material, never config values (key names only), never content, never the actor's own
  identity (it belongs on the erasable actor label, not in the sealed payload). `error_detail`
  comes from `scrub_error_detail(exc)` or a fixed system-authored string, never `str(exc)`.
- **Never swallow an audit write.** It is fail-closed: a record failure must fail the action. No
  `try`/`except` that turns it into success, and a broad handler that reports errors to a user
  or model must let `AuditCaptureError` through.
- **Evidence of a failed or denied attempt uses `record_event_now`.** A `record_event` in a
  session that is about to roll back rolls the evidence back with it.
