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

1. **The sandbox binaries.** Each bundled activity's `sandbox.wasm` is compiled from its source.
   The binaries are not in git, and an activity whose binary is missing fails at launch.
2. **A shared secret.** `PXC_LAUNCH_SECRET` here and `SPARKTH_PXC_LAUNCH_SECRET` on the Open edX
   side must hold the same value. A mismatch fails every learner's launch with a 401, logged
   here as a signature mismatch.
3. **The XBlock**, installed as above.
4. **Persistent storage.** `PXC_DATA_DIR` holds all learner state and all generated activities.
5. **The build toolchain.** Activities compile on the server, with `compile.mjs` and the
   `node_modules` under `PXC_TOOLCHAIN_DIR`, and `node` on `PATH`.

`.env` is the source of truth for every setting and carries a comment on each one; this file
does not repeat the list.

## Placing one in a course

An author places an activity from a course design conversation:

1. The agent lists the activities the author can place: the bundled samples, then the author's
   own activities by title.
2. The author picks one. If they pick none, `PXC_DEFAULT_ACTIVITY` is placed.
3. Sparkth creates a new placement for it, with its own id and its own learner data.
4. The course gets a `pxc` block that holds only that id. The installed XBlock shows the
   activity through it.

An author can place only their own activities and the bundled samples. Sparkth checks this
again when it places the activity, so an id from anywhere else is refused. Publishing the unit
is covered by the
[XBlock README](../../../third_party_plugins/openedx/xblock/README.md).

## Building an activity from chat

The plugin registers the `pxc-activity-builder` chat job with its system prompt, the scope the chat
classifier reads, and the `pxc` tool category. A conversation routed to the job binds only the
tools in that category. Its contract: the author describes an activity in plain words, and the
agent builds it and replies with a preview link that opens the activity on the Sparkth
`/dashboard/pxc` page.

| Tool | Returns |
|---|---|
| `pxc_about` | The contract: file rules and the manifest JSON schema |
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

The job's prompt lives in `assets/pxc_activity_building_system_prompt.txt` and caps build
attempts at three. The contract text lives in `assets/about.txt`, and the scope the classifier
reads in `assets/pxc_activity_building_scope.txt`.

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
