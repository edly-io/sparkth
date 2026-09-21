# Implementing an analytics event

Read this once the developer has decided which events to add. Deciding *what* to record is in
[SKILL.md](SKILL.md) — start there.

## Choosing the seam

| Where the thing happens | How to emit |
|---|---|
| A route that **returns** | `background_tasks.add_task(...)`, queued after all functional background work |
| A route that **raises** (`HTTPException`) | Background tasks are **discarded** — FastAPI only attaches them to a response that is returned. Needs a detached task or an exception-handler seam |
| Inside a detached task (e.g. the stream processor) | `await` the helper directly, outside any `try`/`except` guard |
| A service or classifier with no `BackgroundTasks` | Give it a scheduling seam — see `ChatTurnAnalytics` in `sparkth/plugins/chat/analytics.py`. Never `await` inline in a request path |

**One seam per set of events that share their identity fields.** `ChatTurnAnalytics` carries
provider and model because every turn event needs them. Events that do not — the attachment
events carry neither, and the routes emitting them have no LLM config to read them from — get a
sibling seam (`ChatAttachmentAnalytics`), not optional fields bolted onto the existing one. A
seam whose fields are half-populated tells a reader nothing about which events it serves.

Two traps worth stating explicitly, because both have shipped as bugs here:

- **Queue analytics last.** Starlette runs the background queue as a plain sequential loop with
  no per-task isolation. An emit queued *ahead* of real work lets an analytics outage silently
  stop that work.
- **Never emit inside a `try`/`except` that handles the request's own failures.** A failed
  analytics write caught by that handler becomes the user's error. In the streaming path this
  wrote a fake error into the instructor's transcript.

## The seam may not know what happened yet

Expect this to be most of the work, and budget for it before promising a small change.

An event records that something *happened*, but the code at the seam frequently cannot say
whether it did:

- an upsert-safe write returns the row whether or not it created it (`attach_document`)
- a delete returns nothing, and destroys the evidence of what it removed (`detach_document`)
- a filter discards what it filtered before any caller sees it (`list_conversation_attachments`)
- a skip is computed, logged, and thrown away (`attach_owned_documents`)

Instrumenting these means changing the seam to report its own outcome — a return-type change,
not a call added. That is the right change and it is worth making: a method that quietly does
one of two different things is hard to reason about regardless of analytics.

But price it honestly. A return-type change reaches every caller **and every test double**.
Widening `list_conversation_attachments` from a list to a ready/unusable split broke sixteen
mocks across five test files that had nothing to do with attachments. Search for stubs of the
method before you start, and change them by their patch target — a blunt find-and-replace on
`return_value=[]` will silently rewrite a neighbouring mock of a different method.

## Emitting more than one event at once

A group of related events — a completion and one event per tool it executed — goes through a
single `emit_events` call. `emit_event` opens its own session per call, so emitting a variable
number of events one at a time costs a session each and lands them in sequence, where the first
failure drops everything behind it. `emit_events` takes the group, acquires the session once,
and commits it as one transaction.

## Tests

Drive the real endpoint and assert on rows that actually landed in `raw_events` — see
`sparkth/plugins/chat/tests/test_analytics_producers.py`. Asserting that a mocked emit helper
was called proves the call site exists, not that a row is produced.

Prove the test has bite: delete the emit and confirm the test fails. On a seam that raises,
that check is mandatory — a test written against the happy path passes while the feature is
entirely broken.

A test that asserts on rows written from a detached task must join that task first, not yield
to the event loop and hope. The streaming tests use `live_stream_tasks` for this; a fixed number
of `asyncio.sleep(0)` calls is not a substitute, because the writes go through database worker
threads rather than loop turns.
