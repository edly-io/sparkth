# Document retrieval in chat

When a user attaches documents to a conversation, the assistant can answer from their content
rather than from the model's own knowledge. Retrieval is not automatic: it runs only when the
conversation has documents to search and only when the user's message needs them.

## When retrieval runs

Both conditions must hold.

**The conversation has at least one usable document.** `ChatService.list_conversation_attachments`
selects documents joined to the conversation whose status is `READY` and that are not deleted. A
document still being ingested, one whose ingestion failed, and one the user has deleted are all
invisible here, so none of them can trigger retrieval. With no such document the turn skips
retrieval without asking anything.

**The message needs those documents.** `RAGSearchClassifier.requires_search` puts the message to
a model together with each document's section headings, and answers yes or no. "Explain
mitochondria" against a document that has such a section is a yes; "make that punchier", a short
confirmation, or a question unrelated to the attached material is a no. A declined search is
logged with the reason the model gave and the conversation UUID; the client is told retrieval was
skipped, not why.

An empty message with documents attached does not retrieve. A document sent with no words is a
valid turn — the scope classifier treats it as one — but there is no question to search for.

## What gets searched

Exactly the documents from the first condition. The route turns them into `drive_file` blocks and
the stream processor reads those blocks back out, so the set the classifier judged is the set
retrieved from. There is no second source of document ids.

## When the decision fails

A classifier failure raises `RAGSearchError`, and the turn ends with an error the user sees and
that is persisted to the conversation. Retrieval is never guessed at: answering from the model's
own knowledge while the user believes their document was consulted is worse than an error.

This is the opposite of how scope is handled — `MessageScopeClassifier` fails *open*, letting a
turn through when it cannot judge it, because the chat model's own system prompt is a second line
of defence there and there is none here.
