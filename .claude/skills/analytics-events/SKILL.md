---
name: analytics-events
description: Use when adding, changing or removing a Sparkth analytics event — instrumenting a route, service seam, classifier or plugin feature, filling a gap where something happens but nothing is recorded, or changing an existing event's payload, timing or emission point. Also when deciding whether something is worth recording at all.
---

# Analytics Events

**You propose events. The developer decides.** This skill is how to make a proposal worth
deciding on. Everything about the events themselves — analytics vs audit, payload safety,
timing, seam choice, batching, the testing standard — is in
[`docs/guides/analytics-events.md`](../../../docs/guides/analytics-events.md).

**Read that guide before writing any code.** Do not work from this file alone.

## The developer owns the vocabulary

An event type is a permanent public contract. Once rows exist, dashboards and queries depend on
the name, the fields and their meaning, and changing any of them is a versioned migration of
everyone's saved queries. That decision is not yours.

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

## What the proposal must answer

Taken from the guide's *Before adding one* — answer all four in the proposal itself:

- **What question cannot be answered today?** If an existing event already answers it, propose
  nothing.
- **Where is the denominator?** A count without one answers nothing.
- **Is it derivable from an event we already emit?** If yes, prefer the one event.
- **What does it cost?** Say the volume out loud.

## Two rules you must not violate while building

Both are explained in the guide; neither is a judgement call.

- **Payloads carry identifiers, lengths, flags and system-authored names only.** Never content,
  titles, filenames, prompts, model-authored reason strings, tool arguments or exception
  messages. If a human or a model wrote the string, it does not go in a payload.
- **Never catch around an emit.** No `try`/`except` around an emit, no bare `except Exception` in
  the write path. A failed analytics write propagates by design. Recording a *failure* is the
  exception that proves this: the emit sits inside the handler that caught the user's error, so
  it is handed to a detached task rather than awaited — see *Recording a failure* in the guide.
