---
name: analytics-events
description: Use when adding, changing or removing a Sparkth analytics event — instrumenting a route, service seam, classifier or plugin feature, filling a gap where something happens but nothing is recorded, or changing an existing event's payload, timing or emission point. Also when deciding whether something is worth recording at all.
---

# Analytics Events

**You propose events. The developer decides.** Everything below is how to make a proposal
worth deciding on, and how to build one correctly once it has been chosen.

The mechanics — declaring an `AnalyticsEventSchema`, namespacing `event_type` under the
plugin, `register_event_schema`, `emit_event` — are in
[`docs/guides/plugins.md`](../../../docs/guides/plugins.md) and the README. Read those for
*how*. This skill is *what, where, and whether*.

## The developer owns the vocabulary

An event type is a permanent public contract. Once rows exist, dashboards and queries depend
on the name, the fields and their meaning, and changing any of them is a versioned migration
of everyone's saved queries. That decision is not yours.

Never add, rename, split, merge or drop an event on your own judgement. Put a proposal to the
developer: the event name, every field, what question it answers, and what it costs. Then wait
for an answer.

**A proposal already written down is not a decision.** An event set spelled out in an issue —
even one the developer filed themselves — is still a proposal until they say to build it. Ask
once, naming anything the issue left open, and take the answer as the decision. Do not treat
your own earlier draft as an approval.

**Red flags — stop and ask:**

- You are about to write `class Something(AnalyticsEventSchema)` and nobody named that event
- You are choosing between one event with a `reason` field and two separate events
- You are adding "just one more field" to an existing schema
- The developer asked for one event and you think two would be better
- You are inferring the event set from an issue description rather than confirming it

**All of these mean: propose, then wait.** Recommending is your job — a proposal with no
recommendation is unhelpful. Deciding is not.

| Rationalization | Reality |
|---|---|
| "The issue says what's needed" | An issue states a problem. The vocabulary is a separate decision. |
| "It's obviously two events" | Say so, and say why. Then let them choose. |
| "I'll add it and they can rename it later" | Renaming after rows exist breaks every query built on it. |
| "It's just one extra field" | Every field is a permanent contract and a payload-safety decision. |
| "They're busy, I'll pick the sensible default" | An unasked question costs a message. A wrong event costs a version bump. |

## Analytics or audit? They fail differently on purpose

Sparkth has two event systems with deliberately opposite failure semantics. Pick before you
design anything.

| | Audit (`sparkth/lib/audit/`) | Analytics (`sparkth/lib/analytics/`) |
|---|---|---|
| Write fails | **Fail-closed** — the action does not proceed | Fail-open — the request succeeds, the error is logged |
| Ordering | Record committed *before* the handler runs | Emitted after the response |
| For | Security-relevant and AI actions: evidence | Rates, trends, funnels: measurement |
| Basis | NIST AU-5, ADR-0002 | Must not affect the request being measured |

**The rule:** if losing one record is unacceptable — compliance, security, "who did this" —
it is an audit event and already fail-closed. If the value is in the rate rather than any
single row, it is analytics.

Do not argue for making an analytics event fail-closed to stop data loss. It does not stop it:
when the analytics database is unreachable the row cannot be written either way, so failing the
request loses the event *and* breaks the product. Only audit's ordering — record first, then
act — gives integrity, and it costs a hard dependency on a write. Analytics runs against a
**separate** database (`ANALYTICS_DATABASE_URL`), so that dependency would put course authoring
behind a metrics pipeline's maintenance window.

Analytics counts here are lower bounds by design: events queued on `background_tasks` are
discarded whenever a route raises (see the "Known gap" note in
`sparkth/plugins/chat/analytics.py`). If a proposed event cannot tolerate that, it is
audit-grade — route it to audit rather than hardening analytics.

## Before proposing, answer these

- **What question cannot be answered today?** If an existing event already answers it, say so
  and propose nothing. Check carefully: `chat.completion_served.rag_used` looks like it covers
  "was retrieval skipped", but `false` cannot distinguish *declined* from *nothing to search*.
- **Where is the denominator?** A count without one answers nothing. "Refusal rate" needs the
  turns that were *not* refused, which usually means emitting on every decision rather than
  only the negative one.
- **Is it derivable from an event we already emit?** If yes, two events for one fact means an
  invariant somebody has to monitor. Prefer one.
- **What does it cost?** Roughly one row per occurrence. Say the volume out loud in the
  proposal.

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
classic trap — it reads like metadata and quotes the user's message. Leave it in logs.

`extra="forbid"` on the base schema rejects unexpected *keys*. It cannot tell that a permitted
field holds course content. That part is on you.

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
that nothing records the moment. That is a real answer, not a fallback. What is wrong is letting
it default silently, because then you cannot tell which events were timed and which were not.

## Never catch

No `try`/`except` around any emit, and no bare `except Exception` anywhere in the write path. A
failed analytics write propagates by design — it surfaces as a logged unhandled task error
rather than being hidden. Emission runs after the response, which is what makes that safe.

Propagating is not the same as fail-closed: the request has already succeeded by the time the
emit runs, so the failure is loud in the logs and invisible to the user. That is the intended
outcome for analytics — see *Analytics or audit?* above. Catching it instead would swap a loud
failure for a silent one, which is the one option that is always wrong.

## Building it

Seam choice, batching, and the testing standard are in
[implementation.md](implementation.md) — read it once the events are agreed.

New event types are rows in the existing `raw_events` table. **No migration.**
