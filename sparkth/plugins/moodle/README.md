# Moodle plugin

Publishes chat-authored courses into a Moodle site, exposing course, section, page and quiz
authoring as MCP tools.

The tools act on the **target Moodle**, not on Sparkth, so a Moodle that is not set up
correctly fails in a way that reads like a Sparkth bug. Work through this guide in order.

## Before you start

The Moodle site needs Sparkth's companion plugin installed and its web services turned on.
Follow [`third_party_plugins/moodle/README.md`](../../../third_party_plugins/moodle/README.md)
first and come back here.

You will also need a Moodle site administrator to carry out Steps 1 to 3 — they cannot be done
from a normal account.

## Step 1 — Create the account Sparkth will publish as

Create a dedicated Moodle account for this. Do **not** use a site administrator account: the
token is included in the prompt sent to your AI provider on every chat request, so a leaked
token should be limited to what an ordinary account can do.

The account needs all eight of these permissions:

| Permission | Needed for |
|---|---|
| `webservice/rest:use` | Making any call at all |
| `moodle/course:create` | Creating the course |
| `moodle/course:view` | Working in a course it just created |
| `moodle/course:manageactivities` | Adding sections and placing activities |
| `mod/page:addinstance` | Adding page activities |
| `mod/quiz:addinstance` | Adding quiz activities |
| `moodle/question:add` | Adding quiz questions |
| `mod/qbank:addinstance` | Storing quiz questions on Moodle 5.0 and later |

**Assign the stock `Manager` role at system level.** Go to **Site administration → Users →
Permissions → Assign system roles → Manager** and add the account. This covers seven of the
eight.

**Then allow `webservice/rest:use` explicitly.** No role has it by default. Site administrators
have it implicitly, which is why the gap stays invisible until a normal account is tried. Go to
**Site administration → Users → Permissions → Define roles → Manager → Edit**, search for
`webservice/rest:use` and set it to Allow.

Two roles that look like the right choice and are not:

- **Course creator** can create a course but cannot add anything to it.
- **Teacher** is granted one course at a time, so it never applies to a course that does not
  exist yet.

## Step 2 — Authorise the account on the Sparkth publishing service

A valid token is not enough on its own — the service only accepts accounts that have been
listed on it.

Go to **Site administration → Server → Web services → External services**, find **Sparkth
publishing**, click **Authorised users**, and add the account from Step 1.

Missing this step is the most common setup failure, and Moodle's error message does not say
what is wrong.

## Step 3 — Create the token

Go to **Site administration → Server → Web services → Manage tokens → Create token**. Select
the account from Step 1 and the **Sparkth publishing** service. Leave the IP restriction and
expiry blank unless your organisation requires them.

Copy the token now. Moodle tokens work across the whole site and do not expire by default, so
treat one like a password: reissue it if it leaks, and delete tokens you no longer use.

## Step 4 — Enter the details in Sparkth

Open the Moodle plugin settings in Sparkth and fill in:

| Field | Value |
|---|---|
| Moodle API URL | The site address, for example `https://moodle.example.com` |
| Moodle API key | The token from Step 3 |

Each Sparkth user enters their own details, so everyone publishes as their own Moodle account.
Use a separate Moodle account and token per person rather than sharing one.

## Check the connection

Ask the chat to connect to Moodle. A working setup reports the site name and the username of
the account from Step 1. Then publish a short course and confirm it appears on the site.

## If it does not connect

| What you see | What to fix |
|---|---|
| Access control error on every request | `webservice/rest:use` was not allowed in Step 1 |
| Access exception on every request | The account was not authorised on the service in Step 2 |
| No permission when creating a course | The account is missing `moodle/course:create` |
| No permission when adding a section | The account is missing `moodle/course:manageactivities` |
| No permission when adding a page or quiz | The account is missing `mod/page:addinstance` or `mod/quiz:addinstance` |
| No permission when adding quiz questions | The account is missing `moodle/question:add`, or `mod/qbank:addinstance` on Moodle 5.x |
| Course is created, then the next step fails | The account is missing `moodle/course:view` |
| Cannot reach the site | The API URL is wrong, or the site is not reachable from where Sparkth runs |

## What to expect when publishing

- A course created this way does not automatically show up in the publishing account's own
  course list. Open it from the course search or the link Sparkth reports.
- Sparkth adds sections one at a time and does not check the site's maximum-sections setting, so
  a long course can end up with more sections than an administrator intended.
- On Moodle 5.x, quiz questions are stored in a question bank Sparkth creates for itself rather
  than the course's default question bank, so they will not be listed there.
