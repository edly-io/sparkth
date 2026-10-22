# PXC

Hosts PXC activities — portable, sandboxed learning activities — and serves them to learners
inside another LMS's course page. Every answer, score and piece of progress stays here; the
course holds only a reference to the activity.

## This plugin is one half of an integration

Enabling it in Sparkth is not enough to put an activity in a course. The other half is an
integration **installed into the LMS**: it renders the activity inside a course page and mints
the signed launch token this plugin verifies. Without it, the LMS cannot show a placed activity
and a learner sees nothing at all.

Each integration has its own guide beside this file:

- [Open edX](openedx-integration.md)

This README covers only the Sparkth side.

## What a working deployment needs

1. **The sandbox binaries.** Each bundled activity's `sandbox.wasm` is compiled from its source.
   The binaries are not in git, and an activity whose binary is missing fails at launch. The
   Docker image compiles them. To build them manually, run `make pxc.activities.build`.
2. **A shared secret.** `PXC_LAUNCH_SECRET` here and the LMS integration's launch secret must
   hold the same value. A mismatch fails every learner's launch with a 401, logged here as a
   signature mismatch.
3. **The LMS integration**, installed as above.
4. **Persistent storage.** `PXC_DATA_DIR` holds all learner state and all generated activities.
5. **The build toolchain.** Activities compile on the server, with `compile.mjs` and the
   `node_modules` under `PXC_TOOLCHAIN_DIR`, and `node` on `PATH`.

`.env` is the source of truth for every setting and carries a comment on each one; this file
does not repeat the list.

## Placing one in a course

An author places an activity by asking for it by its title in a chat:

1. The agent lists the activities the author can place: the bundled samples, then the author's
   own activities by title.
2. The author picks one. If they pick none, nothing is placed.
3. Sparkth creates a new activity instance for it, with its own id and its own learner data.
4. The LMS course gets a `pxc` block that holds only that id. The LMS integration shows the
   activity through it.

An author can place only their own activities and the bundled samples. Sparkth checks this
again when it places the activity, so an id from anywhere else is refused.

Sparkth records the first time a generated activity is placed, once the LMS has created its block,
so a placement the LMS refuses leaves the activity a draft. Until then the activity is a draft;
from then on it is placed, for good, even if every block that held it is later removed. Bundled
activities have no record and are never changed by placement. If Sparkth cannot record a
placement, the block is left without the activity's reference and the agent is told to delete it
and place the activity again.

## The Activities page

The plugin adds an "Activities" entry to the sidebar for its dashboard page at `/dashboard/pxc`,
which lists the signed-in author's own activities. The list route reports whether each activity has
been placed in a course, and an author can delete one of their own through the delete route. An
activity's `preview_url` is `/dashboard/pxc?activity=<id>`. The page itself lives in
`frontend/plugins/pxc`. The page marks each placed activity and gives each row a Delete button that
asks for confirmation before calling the delete route.

## Building an activity from chat

The plugin contributes its chat capability: a title, its scope and its prompt section. Its
contract: the author describes an activity in plain words, and the agent builds it and
replies with a preview link that opens the activity on the Sparkth
`/dashboard/pxc` page.

| Tool | Returns |
|---|---|
| `pxc_about` | The contract: file rules and the manifest JSON schema |
| `pxc_build_activity` | The id and preview link of a newly built activity |
| `pxc_update_activity` | The id and preview link of an existing activity, changed in place |
| `pxc_list_activities` | The author's most recent activities (20 by default, set by `PXC_LIST_ACTIVITIES_LIMIT`), newest first, each with id, title, creation time, preview link and whether it is placed |
| `pxc_get_activity_source` | One of the author's activities as its title, description, manifest, `ui.js` and `sandbox.js`, and whether it is placed |
| `pxc_get_activity_failures` | The actions that failed in the author's preview of one activity's live version (20 by default, set by `PXC_ACTION_FAILURE_LIMIT`), newest first, each with kind, action, permission, value, error and time |
| `pxc_run_activity` | The result of the steps the agent gives, run in order on a throwaway store that starts from the manifest's field defaults: each step's events or error, then the state for each permission and the stored fields. At most `PXC_TRIAL_STEP_LIMIT` steps (20 by default), and a report over `PXC_TRIAL_REPORT_LIMIT` characters (20000 by default) is refused, not cut |

A build or update failure is raised, not returned, and the agent reads its message to fix the
files and try again.

Every tool reads the author from the authenticated request, never from an argument. The read
tools, `pxc_run_activity` and `pxc_update_activity` are owner-only: another author's activity is reported as
unknown. The tools need an authenticated chat session; on the unauthenticated `/ai/mcp` endpoint
they fail with `NoAuthenticatedUser`.

## Changing an activity from chat

`pxc_update_activity` changes one of the author's activities in place, under the same id and
preview link. The change reaches every placement of the activity at its next launch.

What an update may change depends on whether the activity is placed:

| Change | Draft | Placed |
|---|---|---|
| `ui.js`, `sandbox.js`, actions, events, title, description | allowed | allowed |
| A new field, or a field's `default` | allowed | allowed |
| A change that is not backward compatible, such as removing a field or changing a field's type, scope or nested schema | allowed | refused |

A changed `default` reaches every activity instance that has no saved value of its own. A saved
value keeps its shape whatever the default is.

Only the preview writes to a draft's state file, unless a hand-edited LMS block points at the
draft (see [Known limits](#known-limits)). A field removal or change clears that file; a change to
a `default` alone leaves it.

A refused update raises `PxcFieldsFrozen`, which names every offending field and tells the agent
to stop and explain the situation to the author. The agent builds a new activity, with its own
id and a distinct title, only after the author agrees. Courses keep the old activity until the
author places the new one. A failed update is retried as an update, never as a new activity.

There is no rollback: an update overwrites the previous version. So before the agent updates a
placed activity, even with a change it accepts, it tells the author that the change reaches every
course using it and cannot be undone, and updates only after the author confirms.

The capability's prompt lives in `assets/pxc_activity_builder_prompt.txt` and caps build
and update attempts at three. A refusal because the activity is placed does not count toward the
cap. The contract text lives in `assets/about.txt`, and the scope the scope gate
reads in `assets/pxc_activity_building_scope.txt`.

## Adding an activity

One directory per activity under `activities/`, each holding a `manifest.json` that declares the
activity's name, fields, actions and events. Nothing in this plugin knows what any particular
activity contains: an activity declares its own starting configuration as the `default` on each
of its fields, and the runtime serves those for an activity instance nobody has configured yet.

## Generated activities

A generated activity's row is keyed by id and owner. Its title, description and `placed_at` can
change; its id never does. Its files live in revision directories,
`PXC_DATA_DIR/revisions/<id>/<rev>/`, where `<rev>` is a time-ordered id minted when the revision
is published. The relative link `PXC_DATA_DIR/activities/<id>` points at the live revision.
Replacing the link is atomic, so a reader sees the whole old revision or the whole new one.

A launch resolves bundled names first, then a generated id from disk by following the link, with
no database read. The embed pins the launch to the revision live when its page renders: it
re-signs the launch token with that revision's id (`rev`), keeping the token's other claims and its
expiry. Every later request of the page, for its UI script, assets, socket and actions, reads that
revision. An open page keeps the revision it rendered until it reloads.

An update prunes the activity's old revisions once their successor has been live for
`PXC_REVISION_RETENTION_SECONDS`. The embed cuts a pinned launch token's lifetime to that value,
so a token from Sparkth or the LMS (`PXC_LAUNCH_TOKEN_TTL_SECONDS` here, and the Open edX block's
`SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS`) never outlives the revision it names. A page whose token
expires is told its session ended and asked to reload.

Three session routes let an author list their activities, open a preview and delete one; another
user's id is a 404. Previews use a fixed course and activity instance, shared by the Student and
Author views.

A delete removes the activity's row and its failure rows, then its live link and revisions, its
learner state file with the `-wal` and `-shm` sidecars, and its storage directory. The row goes
first, in one transaction with a `pxc.activity_deleted` audit event, so a failed audit record
leaves the activity whole. Afterwards, launches and LMS blocks that point at the activity return
404.

## Building an activity

A build runs these steps in order:

1. Validate the source: no assets or capabilities, fixed file names, and the name is set by the
   server.
2. Compile `sandbox.js` against the bundled `pxc.wit`.
3. Smoke-test the result in a child process, on a throwaway store. It reads `getState` as play and
   as edit, runs `config.save` as edit with the fields' defaults when the manifest declares it,
   runs every other action as play and as edit with the simplest value its schema accepts, then
   reads `getState` again. Any error fails the build. The failure lists the failed steps in order,
   up to `PXC_ERROR_LIMIT` characters, and says so when more were cut.
4. Publish the directory as the activity's first revision and point the link at it.
5. Insert the row.

An update runs the first three steps the same way, then:

1. Read the activity's placement and compare the new fields with the live revision's.
2. Refuse the update if the activity is placed and a field was removed or changed.
3. Publish the files as a new revision and swap the link.
4. Clear the state file if the activity is a draft and a field changed.
5. Prune old revisions.
6. Save the title and description.

The manifest is also refused if a field's object type has no properties, since such a field can
only hold `{}`. The failure tells the agent to list the object's keys, or to store a map as an
array of objects with fixed keys.

A failure is written for the authoring agent to act on. Nothing is published before the checks
pass, so a failure before the link swap leaves the activity unchanged. Anything that fails after
it leaves the new revision live: a failure clearing a draft's state file or saving the title and
description is logged and raised, and a revision that cannot be pruned is logged and left for the
next prune.

A compile sees only its own directory, so a sandbox can import only `pxc:sandbox/*`: builtins,
packages and relative paths fail to load. Each step has a timeout and is killed together with its
children. A built directory also holds `sandbox.wasm.bin`, the runtime's compiled-component cache,
so the first learner launch skips that compile.

Concurrency is limited per process, and builds run inside the web container at about 600 MB per
compile.

TODO: move builds to a worker container.

## When an action fails

An action fails when its sandbox throws or writes a value its field or event refuses. It is
refused when the manifest does not accept its name or value. The learner's page then shows a
notice, and the activity gets no events from it. A sandbox failure keeps any field the action
saved before it failed, since each write is stored on its own:

- Over the socket, the server sends `{"error": "action_failed" | "action_rejected", "action": <name>}`
  to the socket that sent the action, and nothing to the others. The socket stays open.
- On the action POST, a sandbox failure and a refusal both answer 422, a status no proxy sends.
  The client drops the action from its queue, so the actions behind it still go. A 502 or other
  5xx, which a proxy sends while the app redeploys, leaves the action queued.

Only an author's preview records a failure. It is stored in `pxc_action_failures`, with its kind
(`failed` or `rejected`), the action, the permission, the value and the error, and the newest
`PXC_ACTION_FAILURE_LIMIT` failures per activity are kept. A learner's failure in a course is never
stored. Every failure and refusal is logged, over the socket and on the POST alike.

## Scores and grading

Scores and all other activity state live in Sparkth's own storage. No LMS gradebook receives a
grade from this plugin.

## Deployment limits

### One worker, for now

An activity's clients exchange events through an in-memory bus inside a single Sparkth
process. Two learners on one activity therefore have to be served by the same process: run
Sparkth with **one** uvicorn worker and one replica, or route by activity instance so that both
parties land together.

With more than one worker the failure is silent. Each learner's actions succeed, each sees
their own events, and neither sees the other's, and no error appears at either end. Sharing the
bus across processes (Redis pub/sub) is the way out and is not built.

### The socket URL's scheme follows the forwarded scheme

`request.url_for` derives `ws` versus `wss` from the scheme of the incoming request. The app
runs under `fastapi run`, whose uvicorn server takes that scheme from `X-Forwarded-Proto` when
the request comes from an address in `FORWARDED_ALLOW_IPS` (default `127.0.0.1`), and only when
the header holds a single scheme. `docker-compose.dev.yml` sets `FORWARDED_ALLOW_IPS` to `*`,
and its bundled nginx forwards the first scheme a TLS-terminating proxy in front of it reports,
else its own.

Any other deployment behind a TLS-terminating proxy or ingress must set `FORWARDED_ALLOW_IPS`
to the proxy's address, and the proxy must send `X-Forwarded-Proto`. Otherwise an HTTPS
learner is seen as `http`, the inline configuration's `ws_url` comes back `ws://`, and the
browser refuses it as mixed content. This is not unique to the socket: `ui_url`,
`asset_base_url` and `action_base_url` are all built from `request.url_for` and share the same
dependency. It matters more here, because a blocked WebSocket kills the activity outright
rather than one asset.

### A socket that drops after the token expires cannot be restored without a reload

`pxc.js`'s `_getWebsocketUrl` returns the cached socket URL unconditionally once one is set,
and its reconnect loop reopens that same URL, so every reconnect presents the same launch
token. Once that token has expired, the server refuses the reconnect's handshake outright and
the client never reaches an open socket at all.

`sparkth-pxc.js` gives up after 30 consecutive failures, roughly a minute on `pxc.js`'s
backoff, and shows a notice telling the viewer to reload. A reload mints a fresh token and
recovers; nothing inside the page can. The ceiling keeps a forgotten tab from costing a refused
handshake every two seconds for as long as it stays open, and it is generous enough that an
ordinary network blip reconnects and flushes the queue instead of tripping it.

The trigger is any network interruption that outlasts the launch token's lifetime, which the
LMS integration sets.

Reloading the configuration inside the page is **not** an available remedy. The configuration
is written into the embed page when it is served, and it carries that page's own launch token
rather than a new one. Recovering inside the browser requires a credential the browser does not
have, so any real fix has to change where the socket's authorization comes from.

## Security

An activity's `ui.js` is third-party code. `pxc.js`'s `_loadScript` loads it with
`await import(url)` into the embed document, so it runs in the same JavaScript realm as the
embed shell; a closed shadow root isolates markup, not script. The embed therefore must not run
on Sparkth's origin, where `frontend/lib/auth-tokens.ts` keeps the signed-in user's bearer token
in `localStorage`.

Two independent layers force an opaque origin:

- The LMS integration's iframe is sandboxed with `allow-scripts allow-forms` and without
  `allow-same-origin`.
- Sparkth serves the embed page and every activity asset with
  `Content-Security-Policy: sandbox allow-scripts allow-forms`. The document gets an opaque
  origin however it is opened: an LMS iframe, an embedding page that grants
  `allow-same-origin`, a direct link, or Sparkth's own preview page.

In an opaque origin the activity code cannot reach Sparkth's `localStorage` or any other storage
or cookie of Sparkth's origin. IndexedDB and `localStorage` throw there, which is why the client
keeps its action queue in memory.

The page needs nothing from Sparkth's origin. Every route it uses authenticates by the launch
token in the query string, never by cookie. The activity configuration is inlined in the embed
page, and the client scripts, the activity assets and the action POSTs answer with
`Access-Control-Allow-Origin: *` (the POSTs also answer their preflight).

The plugin's own errors, such as a 401 for an expired token, carry the same header, so the
client reads the status and shows the same notices as the socket. FastAPI's 422 for a malformed
request, an unhandled 500 and the 403 for a disabled plugin carry no CORS header, so the browser
reports them as a network failure. Each of those leaves the action queued, as does any network
failure. The plugin's 422 for an action that cannot run drops it instead (see
[When an action fails](#when-an-action-fails)).

A refused action is not reported at the moment it is refused. `sendAction` resolves as soon as
the action is in the page's in-memory queue, before any network round-trip, so an activity's own
success message can appear for an action the server has not seen yet. The queue lives only as
long as the page, so an action still queued when the page reloads is lost.

What the viewer does get is a notice once the action is known to be undeliverable. A lapsed
token closes the socket with code 4401 (4000 plus the HTTP status), and a missing activity with
4404. `sparkth-pxc.js` then stops retrying and puts a message at the top of the embed that names
the cause and asks for a reload. Any other drop gets a generic "disconnected" message after a
bounded number of retries.

## Known limits

- Learner actions have no execution limit. That is pxc-lib's to fix.
- `pxc_run_activity` runs the activity's live version only.
- `pxc_run_activity` starts from the field defaults, never from the author's saved preview state,
  so a failure that depends on saved content reproduces only once earlier steps save it.
- The smoke test's sample values do not reach every code path, so a build that passes can still
  fail on a value the activity's UI sends.
- Course staff who edit an LMS block's activity reference directly can point it at any activity
  id, and the LMS signs it. Ownership is checked only when the agent places content. Such a block
  can point at a draft, which is never marked placed, so a later update that changes one of its
  fields clears the learner state that block has saved.
- A placement that lands in the milliseconds between an update's placement check and its link
  swap is not seen by that update. Likewise, two updates of one activity in separate processes can
  swap the link in the opposite order to their revision ids, so a later update's prune can remove
  the revision that was live until that update, under a launch still pinned to it.
- A preview page an author opened before an update keeps the previous revision until it reloads or
  its launch token expires. Anything it saves in that time is written in the previous shape, after
  a draft's preview data was cleared, and a later update that does not change what the activity
  keeps will not clear it again. Reloading the preview avoids it.
- A launch of an activity built as a plain directory is not pinned, since the directory is not a
  revision yet. During the activity's first update, a launch gets a 404 between the directory's
  move and the link's creation. A reload fixes it. A socket opened on the plain directory follows
  the new link, so it can run the new code against the manifest it already read until it
  reconnects.
- Revisions replaced within `PXC_REVISION_RETENTION_SECONDS` before an activity's last update stay
  on disk until its next update.
- "Placed" means placed at least once. Every activity built before placement was recorded shows as
  placed. A block that course staff pointed at a draft by editing it in the LMS shows as not
  placed, yet deleting the draft breaks that block.
- A delete that lands between `pxc_update_activity`'s last ownership check and its link swap
  leaves the update republishing files for an id with no row. Those files are orphaned: nothing
  lists or places them, but embeds would load again.
- A learner request already past its activity check when a delete runs can recreate an empty state
  file. The file is orphaned and harmless.
- A file that cannot be removed is logged and left on disk. If the live link survives, learners
  keep loading the activity, though no row lists or places it.
- A learner socket open when its activity is deleted does not close cleanly: it fails on its next
  action, and its reconnect gets the existing "activity missing" close (4404).
