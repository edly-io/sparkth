# Analytics events

An analytics event is a row recording that something happened, written to a separate analytics
database and read back as a rate, a trend or a funnel. This guide covers the judgement around
one: whether it belongs in analytics at all, what its payload may carry, when it happened, and
which seam can safely emit it.

The mechanics — declaring an `AnalyticsEventSchema`, namespacing `event_type` under the plugin,
`register_event_schema`, `emit_event` — are in the
[plugin development guide](plugins.md). Read those for *how*; this guide
is *what, where and whether*.

An event type is a permanent public contract. Once rows exist, dashboards and saved queries
depend on the name, the fields and their meaning, so adding, renaming, splitting, merging or
dropping one is a decision to make deliberately and not a detail of the change that motivated
it.

## Analytics or audit? They fail differently on purpose

Sparkth has two event systems with deliberately opposite failure semantics. Pick before you
design anything.

| | Audit (`sparkth/lib/audit/`) | Analytics (`sparkth/lib/analytics/`) |
|---|---|---|
| Write fails | **Fail-closed** — the action does not proceed | Fail-open — the request succeeds, the error is logged |
| Ordering | Record committed *before* the handler runs | Emitted after the response |
| For | Security-relevant and AI actions: evidence | Rates, trends, funnels: measurement |
| Basis | NIST AU-5, ADR-0002 | Must not affect the request being measured |

**The rule:** if losing one record is unacceptable — compliance, security, "who did this" — it
is an audit event and already fail-closed. If the value is in the rate rather than any single
row, it is analytics.

Making an analytics event fail-closed does not stop data loss. When the analytics database is
unreachable the row cannot be written either way, so failing the request loses the event *and*
breaks the product. Only audit's ordering — record first, then act — gives integrity, and it
costs a hard dependency on a write. Analytics runs against a **separate** database
(`ANALYTICS_DATABASE_URL`), so that dependency would put course authoring behind a metrics
pipeline's maintenance window.

Analytics counts are lower bounds by design: events queued on `background_tasks` are discarded
whenever a route raises (see the "Known gap" note in `sparkth/plugins/chat/analytics.py`). An
event that cannot tolerate that is audit-grade — route it to audit rather than hardening
analytics.

## Before adding one

- **What question cannot be answered today?** If an existing event already answers it, add
  nothing. Check carefully: `chat.completion_served.rag_used` looks like it covers "was
  retrieval skipped", but `false` cannot distinguish *declined* from *nothing to search*.
- **Where is the denominator?** A count without one answers nothing. "Refusal rate" needs the
  turns that were *not* refused, which usually means emitting on every decision rather than only
  the negative one.
- **Is it derivable from an event already emitted?** If so, two events for one fact means an
  invariant somebody has to monitor. Prefer one.
- **What does it cost?** Roughly one row per occurrence. Know the volume before committing to
  it.

## Payloads carry identifiers, lengths, flags and system-authored names only

Hard rule, no judgement call.

**"Names" means names the system chose** — a tool name, a provider, a model, an enum member.
Never a name a person typed: a document filename, a conversation title, a course name. If a
human or a model wrote the string, it does not go in a payload, however much it looks like
metadata.

So **never** put in a payload: message or course content, conversation or document titles and
filenames, prompts, model-authored reason strings, tool arguments or outputs, or exception
messages.

Record the shape of the thing, not the thing: a length instead of the text, a count instead of
the ids, a bounded enum instead of a free-text cause. A model-authored `refusal_reason` is the
classic trap — it reads like metadata and quotes the user's message. Leave it in the logs.

`extra="forbid"` on the base schema rejects unexpected *keys*. It cannot tell that a permitted
field holds course content.

## Timing

`occurred_at` is when the thing happened, not when the row is written. Emission runs after the
turn it describes — for a streamed turn, minutes after — so a defaulted timestamp puts a
conversation's start after the reply it produced.

Take it from the row that records the thing (`conversation.created_at`, the stored
`Message.created_at`). `received_at` is stamped by the database and is the emission lag, not a
second copy of the event time.

**Some events have no such row.** A deletion destroys the only record of itself; an event for
something that did *not* happen — documents skipped, an attachment passed over — never had one.
There the seam's own clock is the honest answer: capture it at the seam, and say in a comment
that nothing records the moment. What is wrong is letting it default silently, because then you
cannot tell which events were timed and which were not.

## Never catch

No `try`/`except` around any emit, and no bare `except Exception` anywhere in the write path. A
failed analytics write propagates by design — it surfaces as a logged unhandled task error
rather than being hidden. Emission runs after the response, which is what makes that safe.

Propagating is not the same as fail-closed: the request has already succeeded by the time the
emit runs, so the failure is loud in the logs and invisible to the user. Catching it would swap
a loud failure for a silent one.

## Choosing the seam

| Where the thing happens | How to emit |
|---|---|
| A route that **returns** | `background_tasks.add_task(...)`, queued after all functional background work |
| A route that **raises** (`HTTPException`) | Background tasks are **discarded** — FastAPI only attaches them to a response that is returned. Needs a detached task or an exception-handler seam |
| Inside a detached task (e.g. the stream processor) | `await` the helper directly, outside any `try`/`except` guard |
| A service or classifier with no `BackgroundTasks` | Give it a scheduling seam — see `ChatTurnAnalytics` in `sparkth/plugins/chat/analytics.py`. Never `await` inline in a request path |

**One seam per set of events that share their identity fields.** `ChatTurnAnalytics` carries
provider and model because every turn event needs them. Events that do not should get a sibling
seam rather than optional fields bolted onto that one: a seam whose fields are half-populated
tells a reader nothing about which events it serves. (The attachment events are the worked
example — they carry neither field, and the CRUD routes emitting them have no LLM config to read
one from.)

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
- a filter discards what it filtered before any caller sees it
  (`list_conversation_attachments`)
- a skip is computed, logged, and thrown away (`attach_owned_documents`)

Instrumenting these means changing the seam to report its own outcome — a return-type change,
not a call added. That is the right change and it is worth making: a method that quietly does
one of two different things is hard to reason about regardless of analytics.

But price it honestly. A return-type change reaches every caller **and every test double**. When
`list_conversation_attachments` widened from a list to a ready/unusable split, it reached sixteen
mocks across five test files that had nothing to do with attachments — more work than the events
themselves. Search for stubs of the method before you start, and change them by their patch
target: a blunt find-and-replace on `return_value=[]` silently rewrote a neighbouring mock of a
different method when that change was made.

## Emitting more than one event at once

A group of related events — a completion and one event per tool it executed — goes through a
single `emit_events` call. `emit_event` opens its own session per call, so emitting a variable
number of events one at a time costs a session each and lands them in sequence, where the first
failure drops everything behind it. `emit_events` takes the group, acquires the session once,
and commits it as one transaction.

## Tests

Drive the real endpoint and assert on rows that actually landed in `raw_events` — see
`sparkth/plugins/chat/tests/test_analytics_producers.py`. Asserting that a mocked emit helper was
called proves the call site exists, not that a row is produced.

Prove the test has bite: delete the emit and confirm the test fails. On a seam that raises, that
check is mandatory — a test written against the happy path passes while the feature is entirely
broken.

A test that asserts on rows written from a detached task must join that task first, not yield to
the event loop and hope. The streaming tests use `live_stream_tasks` for this; a fixed number of
`asyncio.sleep(0)` calls is not a substitute, because the writes go through database worker
threads rather than loop turns.

## Migrations

New event types are rows in the existing `raw_events` table. **No migration.**
