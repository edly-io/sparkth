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
through the API.

Chat replies and generated course content are written in this language. The preference
is resolved on every request, so changing it applies from the next message onward —
messages already sent are not rewritten.

### What the language applies to

The preference reaches every surface that produces text a user reads:

- **Chat replies** — the assistant answers in this language whatever language the user
  writes in.
- **Generated course content** — titles, descriptions, lesson text, assessment questions,
  answer options and feedback.
- **Conversation titles** — the short titles in the conversation sidebar.

A source document keeps its own language. Uploading an English PDF with a Spanish
preference produces a Spanish course generated from English source: the source is read as
written, and only the output follows the preference.

Internal prompts are deliberately excluded — the scope classifier, the retrieval intent
router and the document search agent all reason in English, the language current models
are strongest in, while handling input in any language. Nothing they produce is shown to
a user.

Two surfaces do not follow the preference yet:

- **API error messages and other fixed backend strings**, including the out-of-scope
  refusal, are still English. These are fixed strings rather than model output, so
  localizing them is separate work that belongs to the static-translation layer — not to
  the language directive the model follows.
- **Course metadata on a publishing target.** A published course carries whatever
  language its destination LMS defaults to; the content itself is in the right language.

### Language and the MCP server

The MCP server authenticates no user, so `get_course_generation_prompt_tool` cannot look
up a preference. It accepts an optional `language` tag instead, which the calling agent
supplies. An omitted tag — or one the platform does not support — uses
`DEFAULT_LANGUAGE`, so a bad value never fails a generation run.

### Output quality varies by language

A language on the supported list means the platform accepts it and generated output in it
has been reviewed by a speaker. It is not a claim that the model is equally strong in
every listed language: measured accuracy drops noticeably in less-represented languages.
This is why the list is short and grows by review rather than by adding whatever the model
claims to speak.

### Supported languages

| Tag | Language |
|---|---|
| `en` | English |
| `es` | Español (Spanish) |
| `fr` | Français (French) |

The list is deliberately short. AI output quality varies by language, so a language
is added only once generated course content in it has been reviewed by a speaker.
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
