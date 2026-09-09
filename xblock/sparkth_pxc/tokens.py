"""The minting half of Sparkth's launch token: how a learner's identity travels to Sparkth.

``sparkth/plugins/pxc/tokens.py`` verifies what this module mints. The two live in
independently installed distributions on different servers and cannot import each other, so
the claim names and the algorithm are duplicated here by necessity; PyJWT carries everything
below them. ``tests/test_tokens.py`` pins what is left of the shared wire format, because a
drift between the two would fail every learner's launch with a 401 instead of failing a test.
"""

from time import time

import jwt

# Must stay in step with the algorithm Sparkth's verifier accepts.
LAUNCH_TOKEN_ALGORITHM = "HS256"


def mint_launch_token(
    activity: str,
    placement: str,
    course_id: str,
    user_id: str,
    permission: str,
    secret: str,
    ttl: int,
) -> str:
    """Return a token carrying these claims, signed with ``secret`` and valid for ``ttl`` seconds.

    ``permission`` is one of PXC's modes — ``"play"`` for a learner, ``"edit"`` for a course
    author. It is a claim inside the signed payload, so the viewer cannot change it.
    """
    claims = {
        "act": activity,
        "plc": placement,
        "cid": course_id,
        "uid": user_id,
        "prm": permission,
        "exp": int(time()) + ttl,
    }
    return jwt.encode(claims, secret, algorithm=LAUNCH_TOKEN_ALGORITHM)
