"""The launch token: how a learner's identity reaches Sparkth from Open edX.

The XBlock mints a short-lived HS256 JWT carrying the Open edX user id, course id and
placement, signed with a secret shared between the two servers; this plugin verifies the
signature and takes the learner's identity from the token, so it never generates or looks up a
user itself. The secret stays server-side at both ends and only the token travels through the
browser, which is what makes the identity trustworthy rather than client-asserted.

The claim names are the plugin's own — ``act``, ``plc``, ``cid``, ``uid`` — since none of the
registered JWT claims describe a placement or an activity type. Only ``exp`` is standard, and
it is PyJWT that enforces it.

Permission is not a claim. It is fixed to ``play`` where the runtime is built, so a caller
cannot ask for ``edit``.

``pxc.lib.signing`` is not used: it reads ``PXC_SIGNING_SECRET`` from the environment and then
unconditionally reassigns it to ``b"dev-insecure-default"``, discarding the configured value
(L8). Reported upstream.
"""

from dataclasses import dataclass
from time import time

import jwt

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.constants import PXC_LAUNCH_SECRET, PXC_LAUNCH_TOKEN_TTL_SECONDS
from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken

logger = get_logger(__name__)

# Pinned on both halves of the token. Passing it to jwt.decode is what refuses a token whose
# header asks for `none`, or for an asymmetric algorithm that would verify against the shared
# secret as a public key.
LAUNCH_TOKEN_ALGORITHM = "HS256"


@dataclass(frozen=True)
class LaunchClaims:
    """Who is asking, and for which placement of which activity."""

    activity: str
    placement: str
    course_id: str
    user_id: str


def _unverified_claims_hint(token: str) -> str:
    """A best-effort ``" (unverified activity=..., placement=...)"`` suffix for a log message.

    Called only after the signature check has already failed, so ``token`` is not proven genuine
    — a forged one can put anything here. Never used to authenticate anything, only to give an
    operator a diagnostic hint (e.g. spotting a shared-secret mismatch, where the token is
    genuine and only the signature side disagrees). Returns "" if the payload cannot be decoded,
    or decodes to something with no activity or placement to show.
    """
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return ""
    activity, placement = claims.get("act"), claims.get("plc")
    if activity is None and placement is None:
        return ""
    return " (unverified activity=%s, placement=%s)" % (activity, placement)


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
    return jwt.encode(claims, secret, algorithm=LAUNCH_TOKEN_ALGORITHM)


def read_launch_token(token: str) -> LaunchClaims:
    """Verify ``token`` against the configured secret and return its claims.

    ``exp`` is required, not merely honoured when present: a launch token without one would be a
    permanent credential sitting in a URL.

    A bad signature is logged at ``warning`` level with a best-effort, explicitly unverified
    activity/placement hint (see ``_unverified_claims_hint``) — the most likely production cause
    is a shared-secret mismatch between Sparkth and the XBlock, which otherwise leaves an
    operator with nothing but learner-reported 401s.

    ``OverflowError`` is caught alongside PyJWT's own errors because it is the one malformed
    token PyJWT does not wrap: it coerces ``exp`` with ``int()``, and a JSON infinity makes that
    raise. Uncaught it would be a 500 where every other bad token is a 401.

    Raises:
        PxcInvalidLaunchToken: if no secret is configured, or the token is malformed, wrongly
            signed, or expired.
    """
    if not PXC_LAUNCH_SECRET:
        logger.error("PXC_LAUNCH_SECRET is not configured; refusing every launch token")
        raise PxcInvalidLaunchToken("Launch tokens are not configured")

    try:
        claims = jwt.decode(
            token,
            PXC_LAUNCH_SECRET,
            algorithms=[LAUNCH_TOKEN_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.ExpiredSignatureError as err:
        raise PxcInvalidLaunchToken("Expired launch token") from err
    except jwt.InvalidSignatureError as err:
        logger.warning("Bad launch token signature%s", _unverified_claims_hint(token))
        raise PxcInvalidLaunchToken("Bad launch token signature") from err
    except (jwt.InvalidTokenError, OverflowError) as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err

    try:
        return LaunchClaims(str(claims["act"]), str(claims["plc"]), str(claims["cid"]), str(claims["uid"]))
    except KeyError as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err
