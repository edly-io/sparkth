# Moodle plugin

Publishes chat-authored courses into a Moodle site over Moodle's REST web services, exposing
course, section, page and quiz authoring as MCP tools.

The tools call web service functions on the **target Moodle**, not on Sparkth, so a misconfigured
Moodle fails in a way that otherwise reads as a Sparkth bug. Work through the prerequisites below
before pointing the plugin at a site.

## Target-site prerequisites

- Enable web services and the REST protocol on the target site.
- Install the `local_sparkth` companion plugin. Its `db/services.php` declares the
  `Sparkth publishing` external service itself — installing the plugin creates the service with
  `enabled => 1`, `restrictedusers => 1`, and all six functions the tools need
  (`local_sparkth_create_section`, `local_sparkth_create_page`, `local_sparkth_create_quiz`,
  `core_webservice_get_site_info`, `core_enrol_get_users_courses` and
  `core_course_create_courses`). No admin step creates or configures the service itself.
- Because the service is `restrictedusers => 1`, a token alone is not enough: an admin must
  explicitly authorise the token's user on the `Sparkth publishing` service in Moodle's admin
  UI. Skipping this step is the most likely first-install failure — every call returns an
  `accessexception` (the tools append a hint saying so to Moodle's own wording, which names no
  cause).
- Mint a token for a user holding all **five** required capabilities: `webservice/rest:use`,
  `moodle/course:view`, `moodle/course:create`, `moodle/course:manageactivities` and
  `moodle/question:add` — and **not** for an admin. The stock `coursecreator` role is **not**
  sufficient: it holds only `moodle/course:create`. No stock role holds `webservice/rest:use`
  (a site admin has it implicitly, which hides the gap) — without it every call fails with a
  `401 Access control exception`. `moodle/course:view` is required too, because creating a
  course over web services does not enrol the creator, so its absence surfaces as `400 Course
  or activity not accessible` on the call right after course creation. Verified working recipe:
  assign the stock **Manager** role at system context (covers `course:view`, `course:create`,
  `course:manageactivities` and `question:add`) plus `webservice/rest:use` granted explicitly,
  to a non-admin user. A Moodle web service token is site-wide and does not expire by default,
  and `MoodleConfig.to_lms_credentials_hint()` puts it in the LLM system prompt, so it is
  transmitted to the configured LLM provider in plaintext on every chat request (see the
  SECURITY NOTE in `sparkth/core/plugins/config_base.py`) — keep the account non-admin so a
  leaked token is bounded by that role.
- `local_sparkth_create_section` gates on `moodle/course:manageactivities`, where core gates the
  same operation on `moodle/course:update` and additionally enforces the site's
  `get_max_sections()` limit. A caller looping on `moodle_create_section` — which is what an LLM
  agent does — can therefore take a course past the section limit the site's admin set.
- On Moodle 5.x, `local_sparkth_create_quiz` creates questions in a `Sparkth question bank` that
  the companion creates for itself, not the course's default question bank, so authored
  questions will not appear there.

## Live test lane

`tests/test_live_moodle.py` is an opt-in end-to-end publish against a real Moodle, run with:

```bash
MOODLE_TEST_URL=http://localhost:8000 MOODLE_TEST_TOKEN=<token> make test.backend.moodle
```

Both variables are read with `os.getenv`, which neither `.env` nor `.env.local` reaches — they
must arrive as real environment variables (exported in your shell, or passed to the make target
as above, which keeps the token out of every tracked file). Setting them in `.env.local` leaves
the lane silently skipped. Without them a plain `uv run pytest` skips the lane, so the default
suite needs no Moodle.
