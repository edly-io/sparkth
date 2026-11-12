"""Fixed values this package shares with Sparkth's verifying half.

Deployment-dependent values are not here: they are Django settings, read through
``django.conf.settings`` because that is how anything inside Open edX is configured.
"""

from pathlib import Path

# Must stay in step with the algorithm Sparkth's verifier accepts.
LAUNCH_TOKEN_ALGORITHM = "HS256"

# The script that sizes an activity's iframe to its content. Sent inline with the block's
# markup, so installing this package needs no static-asset step.
RESIZE_SCRIPT = (Path(__file__).parent / "resize.js").read_text(encoding="utf-8")
