# User management

Users are created and managed from the command line. This is the primary path when
frontend registration is disabled (see [`REGISTRATION_ENABLED`](../reference/configuration.md#registration_enabled)).

## Create a user

```bash
make create-user -- --username john --email john@example.com --name "John Doe"
# Using short flags
make create-user -- -u john -e john@example.com -n "John Doe"
```

If a password is not provided via flag, you'll be prompted to enter it securely.

Create an admin user — grants the global `admin` role (run `make migrations` first so the
role is seeded):

```bash
make create-user -- --username admin --email admin@example.com --name "Admin User" --admin
```

Provide the password directly:

```bash
make create-user -- -u john -e john@example.com -n "John Doe" --password "SecurePass123"
```

Options:

- `--username, -u`: Username (required)
- `--email, -e`: Email address (required)
- `--name, -n`: Full name (optional, defaults to the username)
- `--password, -p`: Password (optional, will prompt if not provided)
- `--email-verified`: mark the user's email as already verified (optional, default: false)
- `--admin` (alias `--superuser`): also grant the user the global `admin` role (optional,
  default: false). The `admin` role must already be seeded (via `make migrations`), or the
  command exits without creating the user. See the [permissions guide](permissions.md) for
  what the `admin` role grants.

## Reset a password

The user is given as a positional username **or** email:

```bash
make reset-password -- john
# Provide the password directly
make reset-password -- john --new-password "NewSecurePass123"
make reset-password -- john -p "NewSecurePass123"
```

Options:

- `identifier`: Username or email of the user (required, positional)
- `--new-password, -p`: New password (optional, will prompt if not provided)

## Preferred language

Each user has a preferred language recorded on their profile: a
[BCP 47](https://datatracker.ietf.org/doc/html/rfc5646) tag, readable and settable
through the API. It selects the language of Sparkth's own interface text — labels,
buttons, and fixed backend messages — from the languages the platform ships
translations for.

### The language of AI-generated text

Chat replies, generated course content, and conversation titles are **not** governed by
this setting. The assistant writes in the language of the user's most recent message and
switches when the user switches, so no configuration is needed and any language the
model handles is available.

- **Chat replies** follow the language the user is writing in.
- **Generated course content** — titles, descriptions, lesson text, assessment questions,
  answer options and feedback — follows the same language.
- **Conversation titles** follow the language of the message the conversation opened with.
- **API error messages and other fixed backend strings** follow the interface language
  rather than the conversation, because no model is involved in producing them. The
  out-of-scope refusal is a special case: the assistant sends it in the language of the
  conversation, while the copy streamed directly by the backend on the same path follows
  the interface language.

A user writing in one language may ask for the course itself in another; the assistant
honours that request for the course content and keeps replying in the language the user
is writing in.

A source document keeps its own language. Uploading an English PDF while writing in
Spanish produces a Spanish course generated from English source: the source is read as
written, and only the output follows the conversation.

Quality varies by language. Sparkth places no restriction on which languages it will
generate in, which means output in a language nobody on the team has reviewed is
possible; large language models are measurably stronger in widely spoken languages than
in low-resource ones.

Internal prompts are deliberately excluded — the scope classifier, the retrieval intent
router and the document search agent all reason in English, the language current models
are strongest in, while handling input in any language. Nothing they produce is shown to
a user.

The **Slack assistant** is a separate case: it answers questions from Slack members, who
are not signed-in Sparkth users, and its prompts carry no language directive at all.

### Language and the MCP server

The MCP server authenticates no user, so `get_course_generation_prompt_tool` has no
conversation to read a language from. It accepts an optional `language` tag instead,
which the calling agent supplies. Any BCP 47 tag is accepted, not only the languages the
interface ships in; an omitted tag, or a value that is not a valid language tag, uses
`DEFAULT_LANGUAGE`. A bad value never fails a generation run.

The tag is the *course's* language and says nothing about the language the agent's own
user speaks — an English speaker may commission a Spanish course, and the agent should
keep asking its clarifying questions in the language of its own conversation.

### Supported languages

| Tag | Language |
|---|---|
| `en` | English |
| `es` | Español (Spanish) |
| `fr` | Français (French) |

The list is deliberately short. AI output quality varies by language, so a language
is added only once generated course content in it has been reviewed by a speaker.
Inclusion is not a claim that the model is equally strong in every listed language:
measured accuracy drops noticeably in less-represented ones.
Matching against the list is an exact, case-sensitive comparison: `en-US` and `EN`
are both rejected as unsupported, not normalised to `en`.

Fetch the current list — and the platform default — from the API. This endpoint needs no
token, so the sign-in and password-reset pages can render in the right language before
anyone has one:

```bash
curl http://localhost:7727/api/v1/languages
```

```json
{
  "languages": [
    {"code": "en", "name": "English", "native_name": "English"},
    {"code": "es", "name": "Spanish", "native_name": "Español"},
    {"code": "fr", "name": "French", "native_name": "Français"}
  ],
  "default": "en"
}
```

### Reading and setting a user's language

`GET /api/v1/user/me` returns `language` as stored: `null` means the user has never
chosen one, which is different from having chosen English. The platform-wide
fallback value is `DEFAULT_LANGUAGE`, configurable and also readable as `default` in
the `GET /api/v1/languages` response (see the
[configuration reference](../reference/configuration.md#default_language)).

Set it with:

```bash
curl -X PATCH http://localhost:7727/api/v1/user/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"language": "es"}'
```

An unsupported tag is rejected with a `422`.

Clear a previously chosen language — so the platform default applies again —
by sending an explicit `null` rather than omitting the field:

```bash
curl -X PATCH http://localhost:7727/api/v1/user/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"language": null}'
```

The new value is stored immediately and returned by subsequent reads.

If a language is later removed from the supported list, a stored tag that is no
longer in the list stops being a valid choice: the value stays in the column, but
it no longer passes the allowlist check, so PATCH rejects it with a `422` if the
user tries to set it again.
