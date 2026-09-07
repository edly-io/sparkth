# sparkth-pxc-xblock

An Open edX XBlock that renders a PXC activity hosted by Sparkth inside a course unit.

The block itself stores no activity data — only the activity type's name and the placement id
that Sparkth minted when the course content was published. When a learner opens the unit, the
block mints a short-lived, signed launch token carrying the learner's Open edX user id, the
course id and the placement id, and renders a sandboxed iframe pointed at Sparkth's embed route
with that token. Sparkth verifies the token's signature, resolves the learner's identity from
its claims, and serves the activity; all activity state (answers, scores, progress) is stored
and stays in Sparkth, and never reaches the Open edX gradebook.

This package is a separate Django distribution. Sparkth's own application never installs it and
never imports it — it is built and iterated here for convenience while the integration is under
development. Whether it eventually moves into the `edly-io/pxc` repository as a remote-backend
mode of the existing `pxc-xblock`, or stays a standalone package, is not yet decided.

## Installing

Install this distribution into the Open edX instance (e.g. `pip install ./xblock`), then add
`pxc` to the course's **Advanced Module List** in Studio's Advanced Settings. Both steps are
required per course — installing the package alone does not enable the block anywhere.

## Django settings

The block reads three settings from the Open edX instance's Django settings:

| Setting | Purpose |
|---|---|
| `SPARKTH_PXC_BASE_URL` | The base URL of the Sparkth instance to embed activities from. |
| `SPARKTH_PXC_LAUNCH_SECRET` | The HMAC secret used to sign launch tokens. **Must be set to the exact same value as Sparkth's `PXC_LAUNCH_SECRET`** — the two sides sign and verify with the same shared secret, and a mismatch fails every learner's launch. |
| `SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS` | How many seconds a minted launch token stays valid. Kept short, since a token is minted fresh on every page render. |

## Scores and grading

Scores and all other activity state live in Sparkth's own storage. This block does not report a
grade to Open edX's gradebook — that integration does not exist yet.

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
