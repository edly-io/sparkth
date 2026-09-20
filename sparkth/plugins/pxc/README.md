# PXC

Hosts PXC activities — portable, sandboxed learning activities — and serves them to learners
inside another LMS's course page. Every answer, score and piece of progress stays here; the
course holds only a reference to the activity.

## This plugin is one half of an integration

Enabling it in Sparkth is not enough to put an activity in a course. The other half is
[`sparkth-pxc-xblock`](../../../xblock/README.md), a separate Django distribution that **must be
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

`.env` is the source of truth for every setting and carries a comment on each one; this file
does not repeat the list.

## Placing one in a course

An authoring agent calls the `openedx` plugin's `openedx_add_plugin_content` tool with
`contributor: "pxc"`. That mints a placement here and asks Studio to create a block of category
`pxc`, which the installed XBlock provides. Studio creates it on the draft branch, so the unit
must be published before a learner sees anything — [`xblock/README.md`](../../../xblock/README.md)
covers that and the Advanced Module List, which is optional and only affects Studio's component
picker.

## Adding an activity

One directory per activity under `activities/`, each holding a `manifest.json` that declares the
activity's name, fields, actions and events. Nothing in this plugin knows what any particular
activity contains: an activity declares its own starting configuration as the `default` on each
of its fields, and the runtime serves those for a placement nobody has configured yet.
`PXC_DEFAULT_ACTIVITY` names the one the content contributor places in a course.
