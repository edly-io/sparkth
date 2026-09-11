# sparkth-pxc-xblock

An Open edX XBlock that renders a PXC activity hosted by Sparkth inside a course unit.

The block itself stores no activity data — only the activity type's name and the placement id
that Sparkth minted when the course content was published. When a learner opens the unit, the
block mints a short-lived, signed launch token carrying the learner's Open edX user id, the
course id and the placement id, and renders a sandboxed iframe pointed at Sparkth's embed route
with that token. Sparkth verifies the token's signature, resolves the learner's identity from
its claims, and serves the activity; all activity state (answers, scores, progress) is stored
and stays in Sparkth, and never reaches the Open edX gradebook.

This package is a separate Python distribution, installed into the Open edX instance rather than
into Sparkth. It is not a Django app — no models, no migrations, no `INSTALLED_APPS` entry — and
neither `XBlock` nor `web-fragments` requires Django; it is depended on only to read the settings
below through `django.conf.settings`, which is how anything inside Open edX is configured.

Sparkth's own application never installs it and never imports it: it is built and iterated here
for convenience while the integration is under development. Whether it eventually moves into the
`edly-io/pxc` repository as a remote-backend mode of the existing `pxc-xblock`, or stays a
standalone package, is not yet decided.

## Installing

Install this distribution into the Open edX instance (e.g. `pip install ./third_party_plugins/openedx/xblock`). That is
what registers the `pxc` entry point, and it is the only step Sparkth's publishing tool needs
— verify it resolved with:

```bash
./manage.py lms shell -c "from xblock.core import XBlock; print(XBlock.load_class('pxc'))"
```

Adding `pxc` to the course's **Advanced Module List** in Studio's Advanced Settings is
optional, and only affects course authors: it is what puts the block in Studio's *Advanced*
component picker. It does not gate blocks created through the Studio API, and it does not
gate rendering in the LMS.

**A published block is required, though.** `openedx_add_plugin_content` creates the block in
Studio's draft branch. The LMS reads the published branch, so until the unit is published the
LMS raises `ItemNotFoundError` for the block and the learner sees nothing at all. Publish the
unit in Studio, or:

```bash
./manage.py cms shell -c "
from opaque_keys.edx.keys import UsageKey
from xmodule.modulestore.django import modulestore
modulestore().publish(UsageKey.from_string('<unit locator>'), <user id>)"
```

## Editing an activity in Studio

**Deploy Sparkth before this XBlock.** Sparkth treats an absent `prm` claim as `play`, so an
older XBlock talking to a newer Sparkth stays safe; the reverse — a newer XBlock talking to an
older Sparkth — renders the editing notice above a *learner* view with no Save button, telling
the author to click a button that is not there.

Click **Edit** on the component. Studio renders the activity in PXC's `edit` mode, where the
author can change the question, the answers and which answers are correct.

**Studio's Save and Cancel buttons do not apply to the activity's content.** The activity
persists a change through Sparkth the moment the author clicks the activity's *own* Save
button, which happens before Studio's buttons are reachable — so Cancel reverts nothing.

This is a consequence of where the content lives, not an oversight. Studio's buttons operate
on XBlock fields, and no XBlock field holds activity content: the course stores only a
reference, and the activity's data stays in Sparkth. Making Cancel behave would mean copying
activity content into XBlock fields, putting the same state in two places and reintroducing
exactly the drift this design avoids. The editing view therefore carries a notice saying so,
because an author has no other way to find out.

By default, Studio renders the editing view only to users who may author the course, and the
launch token it mints carries `edit` inside its signed payload; Sparkth verifies the signature
and takes the permission from the claim. That default holds only while Open edX's
`FEATURES['ENABLE_XBLOCK_VIEW_ENDPOINT']` stays off: with it on, the LMS's `xblock_view`
endpoint renders any `view_name` — including `studio_view` — for any authenticated user with
access to the block, so an enrolled learner can request one directly and receive an `edit`
token.

The launch token's lifetime also bounds how long an editing session can run: it defaults to
300 seconds (`SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS`), and Sparkth refuses a save submitted
after it lapses. The socket re-verifies the token on every action, so this bound applies to a
socket session exactly as it applies to the HTTP routes.

A refused save is not reported to the author as an error, though. `sendAction` resolves as soon
as the action reaches the browser's IndexedDB queue, before any network round-trip, so the
activity's own "Configuration saved!" message can appear for an edit the server went on to
discard. The author is not left with no signal at all, though: a lapsed token closes the
already-open socket with code 1008, which fires `pxc.js`'s `pxc:connection` offline banner — so
what they see is a disconnect indicator contradicting the success message, not silence.

## Django settings

The block reads three settings from the Open edX instance's Django settings:

| Setting | Purpose |
|---|---|
| `SPARKTH_PXC_BASE_URL` | The base URL of the Sparkth instance to embed activities from. |
| `SPARKTH_PXC_LAUNCH_SECRET` | The HMAC secret used to sign launch tokens. **Must be set to the exact same value as Sparkth's `PXC_LAUNCH_SECRET`** — the two sides sign and verify with the same shared secret, and a mismatch fails every learner's launch. |
| `SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS` | How many seconds a minted launch token stays valid. Kept short, since a token is minted fresh on every page render. |

`SPARKTH_PXC_BASE_URL` is fetched by the **learner's browser**, not by Open edX itself — it
goes into the iframe's `src`. It therefore has to be a URL that reaches Sparkth from the
browser. Pointing it at a container-internal host such as `host.docker.internal` yields a
blank iframe and no server-side error at either end.

### Getting the secret to Sparkth

Set `PXC_LAUNCH_SECRET` in Sparkth's `.env.local` (git-ignored, and where the sensitive
values belong) to the same string as `SPARKTH_PXC_LAUNCH_SECRET` here. An environment
variable of the same name overrides it, which is how a containerised deployment supplies it.

An empty secret fails closed: Sparkth refuses every launch with
`401 Launch tokens are not configured`. A secret that is set but does not match this side
gives `401 Bad launch token signature` instead — the two messages are worth telling apart when
a learner reports a launch failure.

## Scores and grading

Scores and all other activity state live in Sparkth's own storage. This block does not report a
grade to Open edX's gradebook — that integration does not exist yet.

## Deployment limits

### One worker, for now

An activity's clients exchange events through an in-memory bus inside a single Sparkth
process. Two learners on one activity therefore have to be served by the same process: run
Sparkth with **one** uvicorn worker and one replica, or route by placement so that both
parties land together.

With more than one worker the failure is silent. Each learner's actions succeed, each sees
their own events, and neither sees the other's — no error appears at either end. Sharing the
bus across processes (Redis pub/sub) is the way out and is not built.

### The socket URL's scheme follows the request's, trusted or not

`request.url_for` derives `ws` versus `wss` from the scheme of the incoming request, and
nothing in this application trusts a forwarded-proto header: there is no
`ProxyHeadersMiddleware` and no `X-Forwarded-Proto` handling anywhere in `sparkth/`, the
Dockerfile, or the Makefile. Behind a TLS-terminating proxy or ingress whose address is not in
uvicorn's trusted `forwarded_allow_ips` (default `127.0.0.1`), an HTTPS learner is seen as
`http`, so the config's `ws_url` comes back `ws://` and the browser refuses it as mixed
content.

Configure the proxy-header trust for any TLS deployment (uvicorn's `--forwarded-allow-ips`, or
an equivalent middleware). This is not unique to the socket — `ui_url`, `asset_base_url` and
`action_base_url` are all built from `request.url_for` and share the same dependency — but it
matters more here, because a blocked WebSocket kills the activity outright rather than one
asset.

### A socket that drops after the token expires does not reconnect on its own

`pxc.js`'s `_getWebsocketUrl` returns the cached socket URL unconditionally once one is set,
and its reconnect loop simply reopens that same URL, so every reconnect presents the same
launch token. Once that token has expired, the server refuses the reconnect's handshake
outright — the client never reaches an open socket to receive a proper close code — and
`pxc.js` retries anyway, on a backoff that caps at 2000 ms. That is a refused handshake every
two seconds, indefinitely, with the offline banner stuck on. The learner has to reload the
unit to mint a fresh token.

The trigger is any network interruption more than `SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS`
(default 300 seconds) after the page rendered. The operator's lever today is raising that TTL;
re-fetching the configuration on a refused handshake and reconnecting with the fresh token it
carries is not implemented.

## Security

The embed iframe is sandboxed with `allow-scripts allow-forms allow-same-origin`.
`allow-same-origin` is required: without it the frame gets an opaque origin, so its `fetch()`
call to Sparkth's own config route becomes cross-origin and is blocked. The same attribute also
means the activity's third-party `ui.js` runs with Sparkth's origin, not an isolated one:
`pxc.js`'s `_loadScript` loads it with `await import(url)` into the surrounding document — a
closed shadow root isolates markup, not script — so `ui.js` executes in the same JavaScript realm
as the rest of the embed shell.

That origin holds more than the shell's own markup. `frontend/lib/auth-tokens.ts` writes the
signed-in user's bearer token to `localStorage` on this same Sparkth origin, so an untrusted
activity's `ui.js` running inside the shell can read it.

This is bounded today, not closed: browsers partition storage for third-party iframes, and only
Sparkth's own bundled sample activity ships, so nothing untrusted actually loads through this
path yet. It stops being bounded the moment a third party can supply an activity's `ui.js`.

The way to close it: `pxc.js`'s `_initIframe` path already exists for this — a nested iframe
sandboxed with `allow-scripts allow-forms` and no `allow-same-origin`, talking to its parent by
`postMessage` instead of a same-origin `fetch()`. `SparkthPXC.connectedCallback` deliberately does
not take that path today. Moving onto it, or serving the embed route from a separate origin so
there is no Sparkth-authenticated `localStorage` to read in the first place, are the two
directions forward.
