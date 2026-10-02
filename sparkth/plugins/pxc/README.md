# PXC

Hosts PXC activities — portable, sandboxed learning activities — and serves them to learners
inside another LMS's course page. Every answer, score and piece of progress stays here; the
course holds only a reference to the activity.

## This plugin is one half of an integration

Enabling it in Sparkth is not enough to put an activity in a course. The other half is
[`sparkth-pxc-xblock`](../../../third_party_plugins/openedx/xblock/README.md), a separate Python distribution that **must be
installed into the Open edX instance**. It is what renders the activity inside a unit and what
mints the signed launch token this plugin verifies. Without it, Studio cannot resolve the `pxc`
block a published activity refers to and a learner sees nothing at all.

That README covers installing it, publishing the unit, and the Django settings the Open edX
side needs. This one covers only the Sparkth side.

## What a working deployment needs

1. **The sandbox binaries.** `make pxc.activities.build` compiles each bundled activity's
   `sandbox.wasm`. They are not in git, and an activity whose binary is missing fails at launch.
2. **A shared secret.** `PXC_LAUNCH_SECRET` here and `SPARKTH_PXC_LAUNCH_SECRET` on the Open edX
   side must hold the same value. A mismatch fails every learner's launch with a 401, logged
   here as a signature mismatch.
3. **The XBlock**, installed as above.
4. **Persistent storage.** `PXC_DATA_DIR` holds all learner state and all generated activities.
   The production compose file mounts the `pxc_data` volume there; any other deployment needs a
   persistent volume at that path. It is local disk, so replicas must share it.
5. **The build toolchain.** Activities compile on the server, from the `node_modules` under
   `PXC_TOOLCHAIN_DIR`, with `node` on `PATH`. `make pxc.activities.build` installs both locally,
   and the image ships them.

`.env` is the source of truth for every setting and carries a comment on each one; this file
does not repeat the list.

## Placing one in a course

An authoring agent lists contributors with the `openedx` plugin's
`openedx_list_content_contributors` tool. The `pxc` entry's `options` are the bundled activities
followed by the author's own, the latter by title. The agent then calls
`openedx_add_plugin_content` with `contributor: "pxc"` and the chosen `option_id`. That mints a
placement here and asks Studio to create a block of category `pxc`, which the installed XBlock
provides. With no `option_id` the placement names `PXC_DEFAULT_ACTIVITY`.

Only an activity's author can place a generated activity: the builder checks ownership again
when it builds, whatever the id's origin. Studio creates the block on the draft branch, so the unit
must be published before a learner sees anything — [`third_party_plugins/openedx/xblock/README.md`](../../../third_party_plugins/openedx/xblock/README.md)
covers that and the Advanced Module List, which is optional and only affects Studio's component
picker.

## The Activities page

The plugin ships a dashboard page at `/dashboard/pxc`, listed in the sidebar as "Activities".
It lists the signed-in author's own activities, newest first, each with a Preview button. Preview
opens `/dashboard/pxc?activity=<id>`, the link the backend returns as `preview_url`.

The preview iframes the activity under the author's session, with a Student/Author toggle:
Student asks the launch route for `play` and Author for `edit`. The iframe's sandbox allows
scripts and forms but not same-origin, so activity code runs in an opaque origin. An id the
author does not own, or whose files are missing, reads as "Activity not found". There is no
delete.

## Building an activity from chat

The plugin registers the `pxc-activity` chat job with its system prompt, the scope the chat
classifier reads, and the `pxc` tool category. Chat routes a conversation to the job when its
first message fits the scope, and the conversation keeps that job. It binds only the tools in
that category. Its contract: the author describes an activity in plain words, and the agent
builds it and replies with a preview link that opens the activity on the Sparkth
`/dashboard/pxc` page.

| Tool | Returns |
|---|---|
| `pxc_about` | The contract: file rules, the manifest JSON schema, and a complete worked example |
| `pxc_build_activity` | The id and preview link of a newly built activity |
| `pxc_list_activities` | The author's activities, newest first, each with id, title, description, creation time and preview link |
| `pxc_get_activity_source` | One of the author's activities as its title, description, manifest, `ui.js` and `sandbox.js` |

A build failure is raised, not returned, and the agent reads its message to fix the files and
try again.

Every tool reads the author from the authenticated request, never from an argument, and the two
read tools are owner-only: another author's activity is reported as unknown. The tools need an
authenticated chat session; on the unauthenticated `/ai/mcp` endpoint they fail with
`NoAuthenticatedUser`.

A built activity never changes: an edit builds a new one.

The job's prompt lives in `assets/pxc_activity_system_prompt.txt` and caps build attempts at
three. The contract text lives in `assets/about.txt`; the example files are read from `mcq` on
every call.

## Adding an activity

One directory per activity under `activities/`, each holding a `manifest.json` that declares the
activity's name, fields, actions and events. Nothing in this plugin knows what any particular
activity contains: an activity declares its own starting configuration as the `default` on each
of its fields, and the runtime serves those for a placement nobody has configured yet.
`PXC_DEFAULT_ACTIVITY` names the one the content contributor places in a course when the author
chooses no activity.

## Generated activities

A generated activity's row is immutable, keyed by id and owner. Its files live under
`PXC_DATA_DIR/activities/<id>/`. A launch resolves bundled names first, then a generated id from
disk, with no database read.

Two session routes let an author list their activities and open a preview; another user's id is
a 404. Previews use a fixed course and placement, shared by the Student and Author views.

## Building an activity

A build runs these steps in order:

1. Validate the source: no assets or capabilities, fixed file names, and the name is set by the
   server.
2. Compile `sandbox.js` against the bundled `pxc.wit`.
3. Smoke-test the result in a child process, calling `get_state` for both play and edit.
4. Move the directory into place.
5. Insert the row.

A failure is written for the authoring agent to act on. An edit builds a new activity under a new
id; the old one is untouched.

A compile sees only its own directory, so a sandbox can import only `pxc:sandbox/*`: builtins,
packages and relative paths fail to load. Each step has a timeout and is killed together with its
children. A built directory also holds `sandbox.wasm.bin`, the runtime's compiled-component cache,
so the first learner launch skips that compile.

Concurrency is limited per process, and builds run inside the web container at about 600 MB per
compile.

TODO: move builds to a worker container.

## Known limits

- Learner actions have no execution limit. That is pxc-lib's to fix.
- Course staff who edit the XBlock's `activity` field directly in Studio or OLX can point it at
  any activity id, and the XBlock signs it. Ownership is checked only when the agent places
  content.
