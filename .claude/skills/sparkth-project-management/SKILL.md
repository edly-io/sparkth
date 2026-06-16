---
name: sparkth-project-management
description: Sparkth conventions for GitHub project management — creating issues, pull requests, and committing LLM-generated code. Use whenever creating or editing a GitHub issue, posting a proposed solution, opening a pull request, or writing/committing code produced with LLM assistance.
version: 0.1.0
---

# Sparkth Project Management

Conventions for managing the Sparkth project on GitHub. Follow these whenever you
create issues, propose solutions, open pull requests, or contribute LLM-generated
code.

## Use the `gh` CLI for all GitHub interactions

All interactions with GitHub MUST go through the `gh` CLI — creating and editing
issues, posting comments, opening and reviewing pull requests, and any other
GitHub operation. Do not rely on the web UI or other clients for actions that
`gh` can perform.

```bash
gh issue create --title "..." --body-file issue.md
gh issue comment <number> --body-file solution.md
gh pr create --title "..." --body-file pr.md
```

## Issue titles describe problems, not solutions

An issue title states **what is wrong**, not how to fix it.

- ✅ `chat_router is registered twice at /api/v1/chat`
- ✅ `Plugin routes return 404 when get_route_prefix is unset`
- ❌ `Remove the duplicate include_router call in main.py`
- ❌ `Add a startup consistency check for plugin registries`

If the title names a code change, a function, or an action verb like "add",
"remove", or "refactor", it is describing a solution — rewrite it to describe the
problem instead.

For **bug** issues, the title states what is broken. For **enhancement** issues,
the title may describe the desired capability rather than a deficiency — but it
must still focus on the *need*, not the implementation approach.

- ✅ `Course dashboard needs a progress summary widget`
- ❌ `Add a ProgressWidget component to the dashboard page`

## Issue descriptions state the problem only — solutions go in a comment

The issue **description** (body) must contain only the problem: a summary,
where it happens (file paths and line numbers), why it matters, and how to
observe or reproduce it. It MUST NOT contain a proposed fix.

Propose the solution in a **separate comment** on the issue:

```bash
# 1. Create the issue with the problem description only
gh issue create --title "chat_router is registered twice at /api/v1/chat" \
  --body-file problem.md

# 2. Propose the fix in a separate comment
gh issue comment <number> --body-file proposed-fix.md
```

This keeps the problem statement stable and reviewable while letting proposed
solutions be discussed, revised, or replaced independently.

## Every issue must carry a supported label

Each issue MUST be assigned at least one of the repository's supported labels.
Apply the label at creation time with `gh issue create --label <name>` (repeatable
for multiple labels), or add it afterward with `gh issue edit <number> --add-label <name>`.

```bash
gh issue create --title "..." --body-file problem.md --label bug
```

The supported labels are those defined in the repository — list the current set
with `gh label list`. At time of writing they are:

| Label | Use for |
|---|---|
| `bug` | Something isn't working |
| `enhancement` | New feature or request |
| `refactoring` | Changes that do not add any feature |
| `documentation` | Improvements or additions to documentation |
| `question` | Further information is requested |
| `help wanted` | Extra attention is needed |
| `good first issue` | Good for newcomers |
| `duplicate` | Already exists |
| `invalid` | Doesn't seem right |
| `wontfix` | Will not be worked on |

`gh label list` is the source of truth; check it before assuming a label exists.

## LLM-generated content must carry an LLM notice

Any content produced with the help of an LLM — code, issue descriptions, issue
comments, PR descriptions — MUST include a notice stating so. This applies to
GitHub text and to committed code alike.

**For GitHub text** (issues, comments, PR bodies), add a line at the end:

```markdown
_This <description|proposed fix|comment> was written with the assistance of an LLM (Claude)._
```

**For committed code**, the commit must carry the standard trailer (already
required by the project's commit conventions). Use the model-specific form that
Claude Code emits, naming the model that produced the code:

```
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

For substantial LLM-generated source files, also include a short comment near
the top of the file noting it was generated with LLM assistance.

## Pull request descriptions follow the template

Every PR description MUST follow the template in
[.github/PULL_REQUEST_TEMPLATE.md](../../../.github/PULL_REQUEST_TEMPLATE.md).
It auto-populates on GitHub; fill in every section:

- **What** — one sentence: what changed and why.
- **Changes** — bullet list of `<type>(<scope>): short description`.
- **How to Test** — numbered, reproducible verification steps.
- **Notes** — migrations, breaking changes, new env vars, dependency bumps (or
  "none").

When creating a PR with `gh`, pass a body built from the template so the
sections are present:

```bash
gh pr create --title "fix(plugins): mount chat_router once via plugin loader" \
  --body-file pr-body.md
```

If the PR description or any part of it was written with LLM help, include the
LLM notice described in the "LLM-generated content" section above.
