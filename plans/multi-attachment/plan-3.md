# Multi-Attachment Phase 3: Fix Per-File RAG Early Exit

## Problem

When multiple drive files are attached and the query matches content only in file 1, the system:

1. Searches file 1 → **finds relevant sections** → replaces block with RAG context → continues loop
2. Searches file 2 → **finds nothing** (similarity below threshold) → emits "I searched **RFL-POL-004...** but couldn't find content..." → **returns early**
3. LLM is never called — file 1's retrieved context is discarded

The root cause is a `return` statement at `app/core_plugins/chat/routes.py:761` inside the per-file loop that exits the entire streaming generator when any single file has no results, regardless of whether other files already produced results.

---

## Root Cause — Code Reference

**File:** [app/core_plugins/chat/routes.py](../../app/core_plugins/chat/routes.py)

The streaming generator `stream_chat_response()` runs a nested loop over all `drive_file` content blocks. For each file it calls `search_with_embedding()` and then checks:

```python
# ~line 728
if not results:
    # ...generate error message for THIS file...
    yield f"data: {json.dumps(done_payload)}\n\n"
    return   # <-- exits the whole generator; LLM never called
```

The check `if not results` is scoped to the current file only. There is no cross-file aggregation — a failure on file N discards all context retrieved from files 1…N-1.

---

## Fix Overview

Track whether **any** file produced results during the loop. Only trigger the "couldn't find content / try less strict matching" early-exit path if the **entire batch** of files returned nothing.

Two-level outcome after the loop:

| File 1 results | File 2 results | Expected behavior |
|---|---|---|
| Found | Found | Pass both to LLM |
| Found | Empty | Pass file 1 context to LLM; skip silent mention of file 2 |
| Empty | Found | Pass file 2 context to LLM; skip silent mention of file 1 |
| Empty | Empty | Return "couldn't find content..." and offer retry |

---

## Implementation Tasks

### Task 1 — Read the streaming handler

**File:** `app/core_plugins/chat/routes.py`

- Read lines 645–838 (`stream_chat_response()`) to get the exact current code before making edits.
- Identify: the per-file loop start, the `if not results:` block, the `return` statement, and the block-replacement line where retrieved chunks are inserted into the message.

---

### Task 2 — Add cross-file result tracking

**Before the per-file loop** (currently around line 661), introduce a flag:

```python
any_file_had_results: bool = False
files_with_no_results: list[str] = []
```

**Inside the loop, after `results` is obtained:**

Replace the current:
```python
if not results:
    # ... generate error, yield done_payload, return
```

With:
```python
if not results:
    files_with_no_results.append(source_name)
    continue   # skip this file, keep processing remaining files
```

And when results ARE found:
```python
else:
    any_file_had_results = True
    # ... existing block-replacement logic ...
```

**After the loop**, add the aggregated failure check:

```python
if not any_file_had_results:
    # All files returned no results — generate the retry message
    searched_names = ", ".join(f"**{n}**" for n in files_with_no_results)
    if similarity_threshold <= 0.15:
        no_chunks_msg = (
            f"I searched {searched_names} with progressively less strict matching "
            f"but couldn't find relevant content. "
            f"The documents may not contain information relevant to your query."
        )
        options = []
    else:
        no_chunks_msg = (
            f"I searched {searched_names} but couldn't find content closely "
            f"matching your query (similarity threshold: {similarity_threshold:.0%}).\n\n"
            f"Would you like me to try again with less strict matching?"
        )
        options = ["Try with less strict matching"]
    # ... build and yield the done_payload as before, then return
```

This preserves the existing retry UX exactly when all files fail, while silently skipping empty files when at least one file matched.

---

### Task 3 — Write the test first (TDD)

**File to create:** `tests/chat/test_multi_attachment_rag.py`

Write a test that:

1. Mocks `rank_sections_for_query` and `search_with_embedding` in `context_service.py`
2. Sets up two `drive_file` blocks in the request message content
3. Configures mock so file 1 returns results and file 2 returns `[]`
4. Calls the streaming endpoint `/api/v1/chat/completions` (or the helper directly)
5. Asserts:
   - The response does NOT contain "couldn't find content" / "Would you like me to try again"
   - The LLM is invoked (or, if mocking LLM too, that the resolved messages include file 1's context)

Also add a test case for the all-fail scenario:
- Both files return `[]`
- Asserts the response contains "Would you like me to try again with less strict matching"
- Asserts the response does NOT proceed to LLM

Confirm tests fail before any implementation changes (red phase).

---

### Task 4 — Implement the fix

Edit `app/core_plugins/chat/routes.py` following the approach in Task 2. Keep the diff minimal:

- Add the two variables before the loop
- Change `if not results: ... return` to `if not results: files_with_no_results.append(...); continue`
- Add `any_file_had_results = True` in the else branch
- Add the post-loop all-fail check

Do not restructure or move any other logic. The section-scanning SSE events (`section_confirmed`, `section_removed`) should still fire only for files that are processed.

---

### Task 5 — Handle the `searching_document` SSE event for skipped files

Currently a `searching_document` event is emitted per file at the start of its processing. After the fix, a file that is processed but yields nothing will be silently skipped (no error shown to the user, which is correct). Confirm that:

- `searching_document` is still emitted for every file that is attempted (it already fires before `search_with_embedding`, so it will still fire)
- No `section_confirmed` events are emitted for the empty file (correct — they only fire when chunks pass the threshold)
- The frontend does not show a broken state for a "started but never completed" document search

If the frontend renders a spinner per `searching_document` event that requires a matching terminal event to close, add a `searching_document_skipped` or reuse an existing terminal event for that file. Check `frontend/plugins/chat/hooks/useChatStream.ts` event handling.

---

### Task 6 — Run tests and build

```bash
make test           # pytest suite must pass
make frontend.build # TypeScript compilation must succeed
```

Fix any failures before committing.

---

### Task 7 — Commit

Stage only the changed files:
- `app/core_plugins/chat/routes.py`
- `tests/chat/test_multi_attachment_rag.py`

Commit message:
```
fix(chat): continue to LLM if any attached file has rag results

Previously, when multiple drive files were attached, the streaming
generator returned early with a "no results" error if any single file
had no matching chunks — even if other files had already produced
relevant content. Now the loop collects per-file outcomes and only
triggers the retry prompt when the entire file batch returns empty.
```

---

## Files to Modify

| File | Change |
|---|---|
| [app/core_plugins/chat/routes.py](../../app/core_plugins/chat/routes.py) | Replace per-file early `return` with aggregated post-loop check |
| [tests/chat/test_multi_attachment_rag.py](../../tests/chat/test_multi_attachment_rag.py) | New test file: multi-file RAG scenarios |

## Files to Read (no modification)

| File | Why |
|---|---|
| [app/rag/context_service.py](../../app/rag/context_service.py) | Understand `rank_sections_for_query` and `search_with_embedding` signatures for mocking |
| [app/core_plugins/chat/schemas.py](../../app/core_plugins/chat/schemas.py) | Understand `ChatCompletionRequest` and content block structure |
| [frontend/plugins/chat/hooks/useChatStream.ts](../../frontend/plugins/chat/hooks/useChatStream.ts) | Verify frontend SSE event handling won't break for skipped-file case |

---

## Out of Scope

- Changing the retry threshold logic (0.45 → 0.3 → 0.15 steps remain unchanged)
- Changing how results from different files are ordered or ranked against each other
- Non-streaming (`stream=false`) path — it uses `_resolve_drive_file_blocks()` which has separate error handling and is not affected by this bug
- Per-file "partial match" messaging (e.g., "File 2 had no relevant content, using File 1 only") — keep it silent; the user cares about the answer, not the per-file breakdown
