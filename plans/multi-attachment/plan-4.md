# Multi-Attachment Phase 4: Backend Fix + UI Polish

---

## Part A — Backend Bug Fix: Strip Unresolved `drive_file` Blocks Before LLM Call

### Problem

After the Plan 3 fix, when two files are attached and only file 1 has matching chunks:

1. File 1's `drive_file` block is correctly replaced in `messages` with RAG text (line 745)
2. File 2 returns no results — the loop `continue`s and its `drive_file` block is **left as-is** in `messages`
3. Phase 2 calls `provider.stream_message(messages, ...)` — the Anthropic API receives a content block of type `drive_file`, which it does not recognise
4. API returns HTTP 400: `Input tag 'drive_file' found ... does not match any of the expected tags`

Error observed:
```
ERROR - Streaming failed: Error code: 400 - {
  'error': {
    'type': 'invalid_request_error',
    'message': "messages.2.content.0: Input tag 'drive_file' found using 'type' does not match any of the expected tags: ..."
  }
}
```

### Root Cause

**File:** `app/core_plugins/chat/routes.py`

`stream_chat_response()` replaces a `drive_file` block with RAG text **only when that file returns results** (lines 739–745). Files that return no results get `continue`d, leaving their `drive_file` blocks untouched in `messages`. Because the Anthropic (and other provider) APIs do not understand `drive_file`, the Phase 2 request fails.

### Fix Overview

After the per-file loop exits and before Phase 2 begins, strip any `drive_file` blocks that are still present in `messages`. These are blocks for files whose searches returned no chunks.

**Location to insert cleanup:** immediately after the `if not any_file_had_results` early-exit block ends with `return` (~line 782) and before the `yield 'generating'` line (~line 784).

```python
        # Strip any drive_file blocks that were not replaced (files with no results).
        # Sending them to the LLM API would cause a 400 invalid_request_error.
        for _m in messages:
            if isinstance(_m.get("content"), list):
                _m["content"] = [
                    _b for _b in _m["content"]
                    if not (isinstance(_b, dict) and _b.get("type") == "drive_file")
                ]
                if not _m["content"]:
                    _m["content"] = [{"type": "text", "text": "[No file content available]"}]
```

Use `_m` and `_b` as loop variable names to avoid shadowing the outer `m` and `b` already in scope.

---

### Task 1 — Read the code

**File:** `app/core_plugins/chat/routes.py`

Read lines 730–790 to confirm exact line numbers and variable names before editing. Verify:
- The `continue` branch for empty results ends at line 734
- The `any_file_had_results` early-exit block ends at line 782 (`return`)
- Line 784 is `yield f"data: {json.dumps({'status': 'generating', ...})}\n\n"`

---

### Task 2 — Write the failing test first (TDD red phase)

**File to modify:** `tests/chat/test_multi_attachment_rag.py`

Add a new test `test_partial_match_no_stale_drive_file_blocks`:

```python
@pytest.mark.asyncio
async def test_partial_match_no_stale_drive_file_blocks() -> None:
    """File 1 has results, file 2 has none — no drive_file blocks must reach the provider.

    Bug: the unresolved drive_file block for file 2 was left in messages after
    the per-file loop, causing a 400 invalid_request_error from the LLM API.
    """
    rag_service = MagicMock(spec=RAGContextService)

    async def rank_sections(session, user_id, file_db_id, query):
        source = "doc1.pdf" if file_db_id == 1 else "doc2.pdf"
        return (source, [0.1] * 384, [{"chapter": None, "section": "Guidelines", "subsection": None}])

    async def search(session, user_id, source_name, query_embedding, **kwargs):
        if source_name == "doc1.pdf":
            return [_make_chunk("Guidelines")]
        return []

    rag_service.rank_sections_for_query = rank_sections
    rag_service.search_with_embedding = search

    # Capture what messages the provider receives
    received_messages: list[list[dict]] = []

    async def capturing_stream(*args, messages=None, **kwargs):
        if messages is not None:
            received_messages.append(messages)
        yield "Hello"
        yield " world"

    provider = MagicMock()
    provider.stream_message = capturing_stream

    unresolved = [
        ChatMessage(
            role="user",
            content=[
                {"type": "drive_file", "file_id": 1},
                {"type": "drive_file", "file_id": 2},
                {"type": "text", "text": "Create a course about guidelines"},
            ],
        )
    ]
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "drive_file", "file_id": 1},
                {"type": "drive_file", "file_id": 2},
                {"type": "text", "text": "Create a course about guidelines"},
            ],
        }
    ]

    async for _ in stream_chat_response(
        provider=provider,
        messages=messages,
        conversation=_make_conversation(),
        service=_make_service(),
        session=AsyncMock(),
        tools=None,
        unresolved_messages=unresolved,
        rag_service=rag_service,
        user_id=1,
    ):
        pass

    assert len(received_messages) == 1, "Provider should have been called exactly once"
    for msg in received_messages[0]:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                assert not (
                    isinstance(block, dict) and block.get("type") == "drive_file"
                ), f"drive_file block leaked into LLM messages: {block}"
```

Run the test and confirm it **fails** (red phase):
```bash
pytest tests/chat/test_multi_attachment_rag.py::test_partial_match_no_stale_drive_file_blocks -v
```

---

### Task 3 — Implement the fix

**File:** `app/core_plugins/chat/routes.py`

After the `if not any_file_had_results and files_with_no_results:` block ends with `return` (~line 782) and before the `yield 'generating'` line (~line 784), insert the cleanup block shown in the Fix Overview above.

Do **not** change anything else. Keep the diff minimal.

---

### Task 4 — Run all tests (green phase)

```bash
pytest tests/chat/test_multi_attachment_rag.py -v
pytest tests/chat/ -v
```

All tests must pass. If any other test breaks, investigate before proceeding.

---

### Task 5 — Commit Part A

Stage only the changed files:
- `app/core_plugins/chat/routes.py`
- `tests/chat/test_multi_attachment_rag.py`

Commit message:
```
fix(chat): strip unresolved drive_file blocks before sending to LLM

When multiple files were attached and some returned no RAG results, their
drive_file content blocks were left in the messages list. The LLM API
(Anthropic) rejected the request with HTTP 400 because drive_file is not
a recognised content block type. Strip any remaining drive_file blocks
after the per-file RAG loop, before Phase 2 begins.
```

---

## Part B — UI Polish: RAG Section Labels, Pill Truncation, Multi-File Display

### Overview of three UI changes

| # | Where | What changes |
|---|---|---|
| B1 | "Taking into context" section (AssistantMessage) | Show `from <filename>` after section name; truncate both to 25 chars |
| B2 | Attachment pill (input box preview + message box) | Hard-truncate file names to 25 chars with `…` in pill label and hover tooltip |
| B3 | User message bubble | Show all attached files (`<first> + N others`), not only the first one |

---

### Task 6 — Add `source` to the `section_scanning` SSE event (backend)

**File:** `app/core_plugins/chat/routes.py`

The `section_scanning` event is yielded once per ranked section, inside the per-file loop. `source_name` is already in scope at that point (set by `rank_sections_for_query`). Add it to the payload so the frontend can display which file each section came from.

Find the line that yields `section_scanning` (currently ~line 697):
```python
yield f"data: {json.dumps({'status': 'section_scanning', 'section': {'type': label, 'name': name}, 'done': False})}\n\n"
```

Replace with:
```python
yield f"data: {json.dumps({'status': 'section_scanning', 'section': {'type': label, 'name': name}, 'source': source_name, 'done': False})}\n\n"
```

No other backend changes are needed for the UI work.

---

### Task 7 — Create a shared `truncate` utility

**File to create:** `frontend/plugins/chat/utils/truncate.ts`

```typescript
/**
 * Truncates a string to `max` characters, appending an ellipsis if needed.
 * Uses the Unicode ellipsis character (…) for single-char width.
 */
export function truncate(text: string, max: number = 25): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}
```

This utility is used by both `Pill.tsx` and `AssistantMessage.tsx`.

---

### Task 8 — Update the `ragSections` and `ChatMessage` types

**File:** `frontend/plugins/chat/types.ts`

Two changes:

**1. Add `source` to `ragSections`:**

Current type (line 23):
```typescript
ragSections?: { type: string; name: string; state: "scanning" | "confirmed" }[];
```

Replace with:
```typescript
ragSections?: { type: string; name: string; source?: string; state: "scanning" | "confirmed" }[];
```

**2. Add `attachments` array to `ChatMessage` for multi-file display:**

After line 17 (`attachment?: TextAttachment | null;`) add:
```typescript
attachments?: TextAttachment[];
```

The existing `attachment` field is kept for backward compatibility; `attachments` is the new array-based field used for display in the user message bubble.

---

### Task 9 — Propagate `source` in `useChatStream.ts` and store all attachments

**File:** `frontend/plugins/chat/hooks/useChatStream.ts`

**Change 1 — propagate `source` on `section_scanning`** (inside `applyStatusEvent`, ~line 83):

Current code:
```typescript
if (parsed.status === "section_scanning" && parsed.section) {
    const section = parsed.section as { type: string; name: string };
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId
          ? {
              ...msg,
              statusText: undefined,
              ragSections: [...(msg.ragSections ?? []), { ...section, state: "scanning" as const }],
            }
          : msg,
      ),
    );
```

Replace the inner assignment with:
```typescript
    const section = parsed.section as { type: string; name: string };
    const source = parsed.source as string | undefined;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId
          ? {
              ...msg,
              statusText: undefined,
              ragSections: [
                ...(msg.ragSections ?? []),
                { ...section, source, state: "scanning" as const },
              ],
            }
          : msg,
      ),
    );
```

**Change 2 — store all attachments on the user message** (inside `handleSend`, ~line 237):

Current code:
```typescript
const userMessage: ChatMessage = {
  id: crypto.randomUUID(),
  role: "user",
  content: message || (attachments.length > 0 ? "Uploaded document(s)" : ""),
  attachment: attachments.length > 0 ? attachments[0] : undefined,
};
```

Replace with:
```typescript
const userMessage: ChatMessage = {
  id: crypto.randomUUID(),
  role: "user",
  content: message || (attachments.length > 0 ? "Uploaded document(s)" : ""),
  attachment: attachments.length > 0 ? attachments[0] : undefined,
  attachments: attachments.length > 0 ? attachments : undefined,
};
```

The `attachment` (singular) is kept so existing code reading it does not break.

---

### Task 10 — Update `Pill.tsx` to hard-truncate file names

**File:** `frontend/plugins/chat/components/attachment/Pill.tsx`

Import the utility:
```typescript
import { truncate } from "../../utils/truncate";
```

Two places need updating:

**1. The visible pill label** (currently `<span className="truncate">{firstAttachment.name}</span>`):

Remove the CSS `truncate` class (no longer needed with JS truncation) and apply the helper:
```tsx
<span>{truncate(firstAttachment.name)}</span>
```

**2. The hover tooltip filenames** (the `attachments.slice(1).map(...)` block):
```tsx
{attachments.slice(1).map((attachment) => (
  <div key={attachment.driveFileDbId || attachment.name}>
    {truncate(attachment.name)}
  </div>
))}
```

---

### Task 11 — Update `UserMessage.tsx` to show all attachments

**File:** `frontend/plugins/chat/components/messages/UserMessage.tsx`

Current code (line 23):
```tsx
<Pill
  attachments={message.attachment ? [message.attachment] : []}
  onPreview={openPreview}
  onRemove={handleRemoveAttachment}
/>
```

Replace with:
```tsx
<Pill
  attachments={message.attachments ?? (message.attachment ? [message.attachment] : [])}
  onPreview={openPreview}
  onRemove={handleRemoveAttachment}
/>
```

`message.attachments` is the new array stored in Task 9. The fallback to `[message.attachment]` handles any pre-existing messages in state that were created before this change.

---

### Task 12 — Update `AssistantMessage.tsx` to show truncated section name + filename

**File:** `frontend/plugins/chat/components/messages/AssistantMessage.tsx`

Import the utility:
```typescript
import { truncate } from "../../utils/truncate";
```

**In the visible list** (lines 56–71), replace the section name `<span>`:

Current:
```tsx
<span className={section.state === "scanning" ? "opacity-50" : ""}>
  {section.name}
</span>
```

Replace with:
```tsx
<span className={section.state === "scanning" ? "opacity-50" : ""}>
  {truncate(section.name)}
  {section.source && (
    <span className="text-neutral-300 dark:text-neutral-600"> from </span>
  )}
  {section.source && truncate(section.source)}
</span>
```

**In the overflow tooltip** (lines 81–90), apply the same pattern to the hidden sections:

Current:
```tsx
<span>{section.name}</span>
```

Replace with:
```tsx
<span>
  {truncate(section.name)}
  {section.source && (
    <span className="text-neutral-300 dark:text-neutral-600"> from </span>
  )}
  {section.source && truncate(section.source)}
</span>
```

---

### Task 13 — Build and verify

```bash
make frontend.build
```

TypeScript compilation must succeed with zero errors. Fix any type errors before committing.

---

### Task 14 — Commit Part B

Stage only the changed frontend files:
- `frontend/plugins/chat/utils/truncate.ts`
- `frontend/plugins/chat/types.ts`
- `frontend/plugins/chat/hooks/useChatStream.ts`
- `frontend/plugins/chat/components/attachment/Pill.tsx`
- `frontend/plugins/chat/components/messages/UserMessage.tsx`
- `frontend/plugins/chat/components/messages/AssistantMessage.tsx`

Also stage the backend file changed in Task 6:
- `app/core_plugins/chat/routes.py`

Commit message:
```
feat(frontend): improve multi-file RAG display and attachment pill UX

- Show "from <filename>" on each RAG section in "Taking into context";
  truncate both section name and filename to 25 chars with ellipsis
- Hard-truncate attachment names in the Pill component (input preview
  and hover tooltip) to 25 chars instead of relying on CSS overflow
- User message bubble now shows all attached files via the Pill
  ("<first file> + N others") instead of only the first file
- Backend: include source_name in section_scanning SSE event so the
  frontend can associate each section with its originating document
```

---

## Full File List

| File | Part | Change |
|---|---|---|
| `app/core_plugins/chat/routes.py` | A + B | Cleanup loop (Part A) + add `source` to SSE event (Task 6) |
| `tests/chat/test_multi_attachment_rag.py` | A | New test for stale drive_file blocks |
| `frontend/plugins/chat/utils/truncate.ts` | B | New shared truncation utility |
| `frontend/plugins/chat/types.ts` | B | `source?` on ragSections; `attachments?` on ChatMessage |
| `frontend/plugins/chat/hooks/useChatStream.ts` | B | Propagate source; store all attachments on userMessage |
| `frontend/plugins/chat/components/attachment/Pill.tsx` | B | Hard-truncate name in label and tooltip |
| `frontend/plugins/chat/components/messages/UserMessage.tsx` | B | Use `message.attachments` array for Pill |
| `frontend/plugins/chat/components/messages/AssistantMessage.tsx` | B | Show `from <source>` on each RAG section with truncation |

## Out of Scope

- Non-streaming path (`_resolve_drive_file_blocks`) — unaffected
- Changing retry threshold or similarity logic
- AssistantMessage Pill (`pillAttachment`) — not part of these requirements
- Per-file partial-match user-facing messaging
