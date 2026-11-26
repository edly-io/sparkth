# Document retrieval in Compose

When an author attaches documents to a conversation, Compose can answer from their content rather than from the
model's own knowledge. Retrieval is a step of the planner's, done by the `rag` agent, and it runs only when the
author's message needs the documents.

## Which documents the planner sees

Every turn lists the conversation's attached documents for the planner and its agents, each with its id and name
(`ComposeService.list_conversation_attachments`). The list holds the documents that are ready and the ones that can't
be read: still being ingested or failed. A deleted document is not listed.

## When retrieval runs

The planner decides from the `rag` agent's description, as it does for every other agent. It gives `rag` a step
before any step that draws on what the attached documents say: a question about them, a summary, or a course,
lesson or assessment built from them. It never gives `rag` a step when no documents are attached, or for chit-chat,
confirmations, phrasing tweaks or anything unrelated to the documents.

## What `rag` returns

`rag` checks each document the request draws on, reads its structure and picks the sections the request needs. Its
reply is data for the next step, never shown to the author: the text of the picked sections, followed by why any
document couldn't be read. A document that is still being ingested, failed, or is missing is explained in the
conversation, not turned into an error.

## What `rag` may read

Only documents that are attached to the conversation the turn belongs to and that the requesting user owns. The route
binds the attached documents' ids for the turn, and the document tools treat any other document as missing.
