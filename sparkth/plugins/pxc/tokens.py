"""The launch token: how a learner's identity reaches Sparkth from Open edX.

The XBlock mints a short-lived token carrying the Open edX user id, course id and placement,
signed with a secret shared between the two servers; this plugin verifies the signature and
takes the learner's identity from the token, so it never generates or looks up a user itself.
The secret stays server-side at both ends and only the token travels through the browser, which
is what makes the identity trustworthy rather than client-asserted.

Permission is not a claim. It is fixed to ``play`` where the runtime is built, so a caller
cannot ask for ``edit``.

``pxc.lib.signing`` is not used: it reads ``PXC_SIGNING_SECRET`` from the environment and then
unconditionally reassigns it to ``b"dev-insecure-default"``, discarding the configured value
(L8). Reported upstream.
"""

import hashlib
import hmac
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from time import time

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.constants import PXC_LAUNCH_SECRET, PXC_LAUNCH_TOKEN_TTL_SECONDS
from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken

logger = get_logger(__name__)


@dataclass(frozen=True)
class LaunchClaims:
    """Who is asking, and for which placement of which activity."""

    activity: str
    placement: str
    course_id: str
    user_id: str


def _b64encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def mint_launch_token(
    activity: str,
    placement: str,
    course_id: str,
    user_id: str,
    secret: str,
    ttl: int = PXC_LAUNCH_TOKEN_TTL_SECONDS,
) -> str:
    """Return a token carrying these claims, signed with ``secret`` and valid for ``ttl`` seconds.

    Sparkth itself only verifies tokens — the XBlock is what mints them in production. This
    lives here so the verification path has something to verify under test, and so both halves
    of the format are defined in one place.
    """
    claims = {
        "act": activity,
        "plc": placement,
        "cid": course_id,
        "uid": user_id,
        "exp": int(time()) + ttl,
    }
    payload = _b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"{payload}.{_sign(payload, secret)}"


def read_launch_token(token: str) -> LaunchClaims:
    """Verify ``token`` against the configured secret and return its claims.

    Raises:
        PxcInvalidLaunchToken: if no secret is configured, or the token is malformed, wrongly
            signed, or expired.
    """
    if not PXC_LAUNCH_SECRET:
        logger.error("PXC_LAUNCH_SECRET is not configured; refusing every launch token")
        raise PxcInvalidLaunchToken("Launch tokens are not configured")

    payload, _, signature = token.partition(".")
    if not payload or not signature:
        raise PxcInvalidLaunchToken("Malformed launch token")

    if not hmac.compare_digest(signature, _sign(payload, PXC_LAUNCH_SECRET)):
        raise PxcInvalidLaunchToken("Bad launch token signature")

    try:
        claims = json.loads(_b64decode(payload))
    except (ValueError, UnicodeDecodeError) as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err

    try:
        if int(claims["exp"]) < int(time()):
            raise PxcInvalidLaunchToken("Expired launch token")
        return LaunchClaims(str(claims["act"]), str(claims["plc"]), str(claims["cid"]), str(claims["uid"]))
    except (KeyError, TypeError, ValueError) as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err
