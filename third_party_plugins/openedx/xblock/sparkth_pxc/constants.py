"""Fixed values this package shares with Sparkth's verifying half.

Deployment-dependent values are not here: they are Django settings, read through
``django.conf.settings`` because that is how anything inside Open edX is configured.
"""

# Must stay in step with the algorithm Sparkth's verifier accepts.
LAUNCH_TOKEN_ALGORITHM = "HS256"
