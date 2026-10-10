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

An author places an activity from a course design conversation:

1. The agent lists the activities the author can place: the bundled samples, then the author's
   own activities by title.
2. The author picks one. If they pick none, `PXC_DEFAULT_ACTIVITY` is placed.
3. Sparkth creates a new activity instance for it, with its own id and its own learner data.
4. The LMS course gets a `pxc` block that holds only that id. The LMS integration shows the
   activity through it.

An author can place only their own activities and the bundled samples. Sparkth checks this
again when it places the activity, so an id from anywhere else is refused.

## The Activities page

The plugin adds an "Activities" entry to the sidebar for its dashboard page at `/dashboard/pxc`,
which lists the signed-in author's own activities. An activity's `preview_url` is
`/dashboard/pxc?activity=<id>`. The page itself lives in `frontend/plugins/pxc`.

## Building an activity from chat

The plugin registers the `pxc-activity-builder` chat job with its system prompt, its scope and
the `pxc` tool category. A conversation routed to the job binds only the tools in that category.
Its contract: the author describes an activity in plain words, and the agent builds it and
replies with a preview link that opens the activity on the Sparkth
`/dashboard/pxc` page.

| Tool | Returns |
|---|---|
| `pxc_about` | The contract: file rules and the manifest JSON schema |
| `pxc_build_activity` | The id and preview link of a newly built activity |
| `pxc_list_activities` | The author's most recent activities (20 by default, set by `PXC_LIST_ACTIVITIES_LIMIT`), newest first, each with id, title, creation time and preview link |
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
of its fields, and the runtime serves those for an activity instance nobody has configured yet.
`PXC_DEFAULT_ACTIVITY` names the one the content contributor places in a course when the author
chooses no activity.

## Generated activities

A generated activity's row is immutable, keyed by id and owner. Its files live under
`PXC_DATA_DIR/activities/<id>/`. A launch resolves bundled names first, then a generated id from
disk, with no database read.

Two session routes let an author list their activities and open a preview; another user's id is
a 404. Previews use a fixed course and activity instance, shared by the Student and Author views.

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

### The socket URL's scheme follows the request's, trusted or not

`request.url_for` derives `ws` versus `wss` from the scheme of the incoming request, and
nothing in this application trusts a forwarded-proto header: there is no
`ProxyHeadersMiddleware` and no `X-Forwarded-Proto` handling anywhere in `sparkth/`, the
Dockerfile, or the Makefile. Behind a TLS-terminating proxy or ingress whose address is not in
uvicorn's trusted `forwarded_allow_ips` (default `127.0.0.1`), an HTTPS learner is seen as
`http`, so the inline configuration's `ws_url` comes back `ws://` and the browser refuses it as
mixed content.

Configure the proxy-header trust for any TLS deployment (uvicorn's `--forwarded-allow-ips`, or
an equivalent middleware). This is not unique to the socket: `ui_url`, `asset_base_url` and
`action_base_url` are all built from `request.url_for` and share the same dependency. It
matters more here, because a blocked WebSocket kills the activity outright rather than one
asset.

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
reports them as a network failure. In every failure the action is not sent and stays queued.

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
- Course staff who edit an LMS block's activity reference directly can point it at any activity
  id, and the LMS signs it. Ownership is checked only when the agent places content.
