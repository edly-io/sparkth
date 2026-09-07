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
