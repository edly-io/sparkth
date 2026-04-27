# Multi-Attachment Phase 5: Persist and Restore Multiple Attachment Names Per Message

---

## Problem

When a user sends a message with multiple files attached and later reloads the conversation,
only one filename is shown in the attachment pill. The `+N others` indicator never appears.

### Root Cause

The database stores only **one** attachment per message:

| Layer | What's stored/returned |
|---|---|
| `chat_messages` table | `attachment_name: str \| None`, `attachment_size: int \| None` |
| `service.add_message()` | Accepts only `attachment_name` and `attachment_size` |
| Routes save logic (line 467–468) | Saves only `msg.attachment.name` / `.size` from the first attachment |
| `MessageResponse` schema | Returns only `attachment_name`, `attachment_size` |
| `useConversation.ts` mapping | Creates at most one `TextAttachment` per message |

Current session messages display correctly because `useChatStream.ts` stores all attachments in
the in-memory `ChatMessage.attachments` array (plan-4 change). But this is never persisted, so
on reload it's gone.

### Fix Overview

1. **Backend request schema**: Add `attachments: list[AttachmentMeta] | None` to `ChatMessage`
2. **DB migration**: Add `attachments_json: str | None` column to `chat_messages`
3. **Service**: Accept and store `attachments_json` in `add_message`
4. **Routes save**: Pass all attachments into `add_message`
5. **Response schema**: Add `attachments: list[dict]` to `MessageResponse`
6. **GET endpoint**: Populate `attachments` when returning messages
7. **Frontend request**: `buildUserMessages` sends all attachment names/sizes
8. **Frontend load**: `useConversation.ts` maps `attachments` from API response

---

## Part A — Backend

### Task 1 — Read the relevant backend code

Read these files/sections before making any changes to confirm exact line numbers and signatures:

- `app/core_plugins/chat/schemas.py` — `AttachmentMeta`, `ChatMessage`, `MessageResponse`
- `app/core_plugins/chat/models.py` — `Message` model (attachment fields)
- `app/core_plugins/chat/service.py` — `add_message` method signature (~line 240–261)
- `app/core_plugins/chat/routes.py` lines 450–470 (message save loop) and 1045–1062 (GET endpoint mapper)

---

### Task 2 — Write failing tests first (TDD red phase)

**File:** `tests/chat/test_multi_attachment_persist.py` (new file)

Create two tests:

**Test 1** — `test_add_message_stores_attachments_json`: Directly call `service.add_message` with
`attachments_json='[{"name":"a.pdf","size":100},{"name":"b.pdf","size":200}]'` and assert the
stored `Message.attachments_json` contains both entries.

**Test 2** — `test_get_conversation_returns_attachments_array`: Create a conversation with two
messages — one with `attachments_json` set (multi-file), one with only `attachment_name` set
(legacy). Call `GET /chat/conversations/{id}` and assert:
- The multi-file message has `attachments` list with 2 entries
- The legacy message has `attachments` list with 1 entry (synthesised from `attachment_name`)
- Neither message has `attachments: null` or `attachments: []` when an attachment is present

Run both tests and confirm they **fail** (red phase):
```bash
pytest tests/chat/test_multi_attachment_persist.py -v
```

---

### Task 3 — Create Alembic migration

**Never edit an existing migration. Generate a new one.**

```bash
alembic revision --autogenerate -m "add attachments_json to chat_messages"
```

Open the generated file and verify the `upgrade` function adds:
```python
op.add_column('chat_messages', sa.Column('attachments_json', sa.Text(), nullable=True))
```

Apply it:
```bash
make migrations
```

---

### Task 4 — Add `attachments_json` field to the `Message` model

**File:** `app/core_plugins/chat/models.py`

After line 123 (`attachment_size: int | None = Field(default=None)`), add:
```python
attachments_json: str | None = Field(default=None, sa_column=Column(Text))
```

No other changes to the model.

---

### Task 5 — Update `AttachmentMeta` and `ChatMessage` request schema

**File:** `app/core_plugins/chat/schemas.py`

**Change 1** — No changes needed to `AttachmentMeta` (name + size is correct).

**Change 2** — Add `attachments` (plural) to `ChatMessage`:

Current (line 56):
```python
attachment: AttachmentMeta | None = None
```

Add after it:
```python
attachments: list[AttachmentMeta] | None = None
```

The existing `attachment` field is kept for backward compatibility with any callers that
already send it.

---

### Task 6 — Update `service.add_message` to accept `attachments_json`

**File:** `app/core_plugins/chat/service.py`

Find the `add_message` method (~line 238). Its current signature ends with:
```python
attachment_name: str | None = None,
attachment_size: int | None = None,
```

Add one more parameter:
```python
attachments_json: str | None = None,
```

In the body, when constructing `Message(...)`, add:
```python
attachments_json=attachments_json,
```

---

### Task 7 — Update routes.py save loop to persist all attachments

**File:** `app/core_plugins/chat/routes.py`

Find the message save loop (~lines 461–469):
```python
await service.add_message(
    session=session,
    conversation_id=conversation.id,
    role=msg.role,
    content=stored_content,
    message_type="attachment" if msg.attachment else "text",
    attachment_name=msg.attachment.name if msg.attachment else None,
    attachment_size=msg.attachment.size if msg.attachment else None,
)
```

Replace with:
```python
all_attachments = msg.attachments or (
    [msg.attachment] if msg.attachment else []
)
import json as _json
attachments_json_str = _json.dumps(
    [{"name": a.name, "size": a.size} for a in all_attachments]
) if all_attachments else None

await service.add_message(
    session=session,
    conversation_id=conversation.id,
    role=msg.role,
    content=stored_content,
    message_type="attachment" if all_attachments else "text",
    attachment_name=all_attachments[0].name if all_attachments else None,
    attachment_size=all_attachments[0].size if all_attachments else None,
    attachments_json=attachments_json_str,
)
```

Note: `json` is already imported at the top of `routes.py` — use that import name rather than
`_json`. Check the existing import name before writing the code.

---

### Task 8 — Update `MessageResponse` schema

**File:** `app/core_plugins/chat/schemas.py`

After line 167 (`attachment_size: int | None`), add:
```python
attachments: list[dict[str, Any]] = Field(default_factory=list)
```

Add `Any` to the existing imports from `typing` if not already present.

---

### Task 9 — Update the GET endpoint to populate `attachments`

**File:** `app/core_plugins/chat/routes.py`

Find the `MessageResponse(...)` constructor in `get_conversation` (~lines 1047–1059):
```python
MessageResponse(
    id=msg.id,
    role=msg.role,
    content=msg.content,
    tokens_used=msg.tokens_used,
    cost=msg.cost,
    created_at=msg.created_at,
    message_type=msg.message_type,
    attachment_name=msg.attachment_name,
    attachment_size=msg.attachment_size,
)
```

Replace with:
```python
MessageResponse(
    id=msg.id,
    role=msg.role,
    content=msg.content,
    tokens_used=msg.tokens_used,
    cost=msg.cost,
    created_at=msg.created_at,
    message_type=msg.message_type,
    attachment_name=msg.attachment_name,
    attachment_size=msg.attachment_size,
    attachments=_parse_attachments(msg),
)
```

Add the helper function near the top of the file (before the router definition):
```python
def _parse_attachments(msg: Message) -> list[dict[str, Any]]:
    """Return all attachment metadata for a message.

    Prefers attachments_json (multi-file). Falls back to attachment_name/size
    for messages stored before the multi-attachment migration.
    """
    if msg.attachments_json:
        try:
            return json.loads(msg.attachments_json)
        except (json.JSONDecodeError, ValueError):
            pass
    if msg.attachment_name:
        return [{"name": msg.attachment_name, "size": msg.attachment_size or 0}]
    return []
```

---

### Task 10 — Run all backend tests (green phase)

```bash
pytest tests/chat/test_multi_attachment_persist.py -v
pytest tests/chat/ -v
```

All tests must pass. Fix any failures before proceeding to Part B.

---

## Part B — Frontend

### Task 11 — Update `buildUserMessages` to send all attachment metadata

**File:** `frontend/plugins/chat/hooks/useChatStream.ts`

Find the `buildUserMessages` function (~line 19). Find where the output message is pushed:
```typescript
out.push({
  role: "user",
  content: contentBlocks,
  attachment:
    attachments.length > 0
      ? { name: attachments[0].name, size: attachments[0].size }
      : undefined,
});
```

Add `attachments` (plural) alongside the existing `attachment`:
```typescript
out.push({
  role: "user",
  content: contentBlocks,
  attachment:
    attachments.length > 0
      ? { name: attachments[0].name, size: attachments[0].size }
      : undefined,
  attachments:
    attachments.length > 0
      ? attachments.map((a) => ({ name: a.name, size: a.size }))
      : undefined,
});
```

The existing `attachment` field is kept so the backend's `message_type` detection
and fallback logic continues to work for single-file messages.

---

### Task 12 — Update `ApiMessage` type and conversation loading mapping

**File:** `frontend/plugins/chat/hooks/useConversation.ts`

**Change 1** — Extend `ApiMessage` interface (currently lines 10–18) to include the new field:
```typescript
interface ApiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  message_type: "text" | "attachment";
  attachment_name: string | null;
  attachment_size: number | null;
  attachments: Array<{ name: string; size: number }> | null;  // ← add this
  created_at: string;
}
```

**Change 2** — Update the message mapping (~lines 89–106) to populate `attachments`:

Current mapping creates only `attachment`:
```typescript
const loaded: ChatMessage[] = data.messages.map((m) => ({
  id: String(m.id),
  role: m.role,
  content: ...,
  attachment:
    m.message_type === "attachment" && m.attachment_name
      ? { name: m.attachment_name, size: m.attachment_size ?? 0, text: m.content }
      : undefined,
}));
```

Replace with:
```typescript
const loaded: ChatMessage[] = data.messages.map((m) => {
  const apiAttachments =
    m.attachments && m.attachments.length > 0
      ? m.attachments
      : m.attachment_name
        ? [{ name: m.attachment_name, size: m.attachment_size ?? 0 }]
        : null;

  return {
    id: String(m.id),
    role: m.role,
    content:
      m.message_type === "attachment"
        ? m.content !== "[File attachment]"
          ? m.content
          : ""
        : m.content,
    attachment: apiAttachments
      ? { name: apiAttachments[0].name, size: apiAttachments[0].size, text: m.content }
      : undefined,
    attachments: apiAttachments
      ? apiAttachments.map((a) => ({ name: a.name, size: a.size, text: m.content }))
      : undefined,
  };
});
```

This:
- Uses the new `attachments` array from the API when present (new messages)
- Falls back to synthesising a single-item array from `attachment_name` (legacy messages)
- Keeps `attachment` (singular) populated so no existing code breaks

---

### Task 13 — Build and verify

```bash
make frontend.build
```

TypeScript compilation must succeed with zero errors and zero new warnings. Fix any type errors
before proceeding.

---

### Task 14 — Commit

Stage only the files changed in this plan:

**Backend:**
- `app/core_plugins/chat/schemas.py`
- `app/core_plugins/chat/models.py`
- `app/core_plugins/chat/service.py`
- `app/core_plugins/chat/routes.py`
- `tests/chat/test_multi_attachment_persist.py`
- The new Alembic migration file under `app/migrations/versions/`

**Frontend:**
- `frontend/plugins/chat/hooks/useChatStream.ts`
- `frontend/plugins/chat/hooks/useConversation.ts`

Commit message:
```
feat(chat): persist and restore multiple attachment names per message

Previously only the first attachment name/size was saved to chat_messages,
so on conversation reload the pill showed only one filename regardless of
how many files were originally attached.

Added attachments_json column to store all attachment metadata as JSON.
Backend now reads msg.attachments (plural) from the request and falls back
to msg.attachment for single-file/legacy payloads. GET conversation returns
an attachments array, synthesising it from attachment_name for old rows.
Frontend buildUserMessages sends all attachment names; useConversation maps
the returned array so the pill shows the correct "+ N others" on reload.
```

---

## File Change Summary

| File | Change |
|---|---|
| `app/core_plugins/chat/schemas.py` | Add `attachments` to `ChatMessage` request; add `attachments` to `MessageResponse` |
| `app/core_plugins/chat/models.py` | Add `attachments_json: str \| None` field |
| `app/core_plugins/chat/service.py` | Add `attachments_json` param to `add_message` |
| `app/core_plugins/chat/routes.py` | Save all attachments; add `_parse_attachments` helper; populate in GET endpoint |
| `app/migrations/versions/<hash>_add_attachments_json_to_chat_messages.py` | New Alembic migration |
| `tests/chat/test_multi_attachment_persist.py` | New test file (TDD) |
| `frontend/plugins/chat/hooks/useChatStream.ts` | Send all attachment metadata in request |
| `frontend/plugins/chat/hooks/useConversation.ts` | Map `attachments` array on load; fallback for legacy rows |

## Out of Scope

- Migrating data in existing rows (legacy messages will show one filename — this is acceptable)
- Changing the `Pill`, `UserMessage`, or `AssistantMessage` components (plan-4 already handles display)
- Changing the RAG retrieval or streaming logic
