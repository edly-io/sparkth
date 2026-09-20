"""The minting half of Sparkth's launch token: how a learner's identity travels to Sparkth."""

from time import time

import jwt

from sparkth_pxc.constants import LAUNCH_TOKEN_ALGORITHM


def mint_launch_token(
    activity: str,
    placement: str,
    course_id: str,
    user_id: str,
    secret: str,
    ttl: int,
) -> str:
    """Return a token carrying these claims, signed with ``secret`` and valid for ``ttl`` seconds."""
    claims = {
        "act": activity,
        "plc": placement,
        "cid": course_id,
        "uid": user_id,
        "exp": int(time()) + ttl,
    }
    return jwt.encode(claims, secret, algorithm=LAUNCH_TOKEN_ALGORITHM)
