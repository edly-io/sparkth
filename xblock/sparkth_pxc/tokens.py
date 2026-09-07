"""The minting half of Sparkth's launch token: how a learner's identity travels to Sparkth.

``sparkth/plugins/pxc/tokens.py`` verifies what this module mints; the two live in
independently installed distributions on different servers and cannot import each other, so
this is a deliberate ~30-line duplication of that module's signing half rather than a shared
import. ``tests/test_tokens.py`` pins the exact wire format — claim names and signature
construction — because a drift between the two would fail every learner's launch with a 401
instead of failing a test.
"""

import hashlib
import hmac
import json
import logging
from base64 import urlsafe_b64encode
from time import time

logger = logging.getLogger(__name__)


def _b64encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign(payload: str, secret: str) -> str:
    return _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


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
    payload = _b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"{payload}.{_sign(payload, secret)}"
