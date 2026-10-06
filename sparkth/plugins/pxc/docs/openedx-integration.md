# Open edX integration

Open edX shows a PXC activity through the `sparkth-pxc-xblock` package. Installing and
configuring it on an Open edX deployment is covered in
[`third_party_plugins/openedx/xblock/README.md`](../../../../third_party_plugins/openedx/xblock/README.md).
This guide covers only what the pxc plugin does for Open edX.

## The shared secret

`PXC_LAUNCH_SECRET` must hold the same value as the XBlock's `SPARKTH_PXC_LAUNCH_SECRET`. Set it
in `.env.local`, or in an environment variable of the same name.

An empty secret fails closed: every launch gets `401 Launch tokens are not configured`. A secret
that does not match gives `401 Bad launch token signature`.

## Launch tokens

The XBlock signs a launch token carrying the learner's Open edX user id, the course id, the
activity instance id and the permission (`prm`). The plugin verifies the signature and takes the
learner and the permission from the claims. A token without `prm` is treated as `play`, so
deploy Sparkth before an XBlock that sends `edit`.

The token's lifetime is set on the Open edX side. The plugin refuses an action sent with a
lapsed token, over HTTP and over the socket alike.

## Placing an activity in a course

An authoring agent calls the `openedx` plugin's `openedx_add_plugin_content` tool with
`contributor: "pxc"`. The `pxc` content contributor mints an activity instance and returns a
block of category `pxc`, which Studio creates on the draft branch. The unit must be published
before a learner sees it.
