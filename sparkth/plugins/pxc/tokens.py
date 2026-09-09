"""The launch token: how a learner's identity reaches Sparkth from Open edX.

The XBlock mints a short-lived token carrying the Open edX user id, course id and placement,
signed with a secret shared between the two servers; this plugin verifies the signature and
takes the learner's identity from the token, so it never generates or looks up a user itself.
The secret stays server-side at both ends and only the token travels through the browser, which
is what makes the identity trustworthy rather than client-asserted.

Permission travels as the ``prm`` claim, inside the signed payload, so a caller still cannot
ask for ``edit`` — altering the claim invalidates the signature. Which permission a launch
gets is decided by the XBlock, the only party that knows whether the viewer may author the
course: ``student_view`` mints ``play`` and ``studio_view`` mints ``edit``. That delegation
holds only while Open edX's ``FEATURES['ENABLE_XBLOCK_VIEW_ENDPOINT']`` stays off, which is the
default — with it on, the LMS's ``xblock_view`` endpoint renders any ``view_name``, including
``studio_view``, for any authenticated user with access to the block, so an enrolled learner
can request one directly and receive an ``edit`` token. The consequence is that the shared
secret grants ``edit`` as well as ``play``.

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

from pxc.lib.permission import Permission

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken

logger = get_logger(__name__)


@dataclass(frozen=True)
class LaunchClaims:
    """Who is asking, for which placement of which activity, and at what permission."""

    activity: str
    placement: str
    course_id: str
    user_id: str
    permission: Permission


def _b64encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def _unverified_claims_hint(payload: str) -> str:
    """A best-effort ``" (unverified activity=..., placement=...)"`` suffix for a log message.

    Called only after the signature check has already failed, so ``payload`` is not proven
    genuine — a forged token can put anything here. Never used to authenticate anything, only to
    give an operator a diagnostic hint (e.g. spotting a shared-secret mismatch, where the token
    is genuine and only the signature side disagrees). Returns "" if the payload cannot even be
    decoded, or decodes to something with no activity or placement to show.
    """
    try:
        claims = json.loads(_b64decode(payload))
    except ValueError, UnicodeDecodeError:
        return ""
    if not isinstance(claims, dict):
        return ""
    activity, placement = claims.get("act"), claims.get("plc")
    if activity is None and placement is None:
        return ""
    return " (unverified activity=%s, placement=%s)" % (activity, placement)


def _read_permission(value: object, activity: str, placement: str) -> Permission:
    """The permission a verified token asks for, degrading to ``play`` when it names none.

    Absent means an XBlock older than the claim; unrecognised means version skew or a bug,
    since the claim sits inside the signed payload. Both take the least privilege rather than
    failing an otherwise legitimate launch. ``activity``/``placement`` are logged alongside an
    unrecognised value so the warning can be correlated to a specific launch, the way
    ``_unverified_claims_hint`` already does for a bad signature.
    """
    if value is None:
        return Permission.play
    try:
        return Permission(str(value))
    except ValueError:
        logger.warning(
            "Launch token asked for unknown permission %r (activity=%s, placement=%s); using play",
            value,
            activity,
            placement,
        )
        return Permission.play


def mint_launch_token(
    activity: str,
    placement: str,
    course_id: str,
    user_id: str,
    permission: str,
    secret: str,
    ttl: int | None = None,
) -> str:
    """Return a token carrying these claims, signed with ``secret`` and valid for ``ttl`` seconds.

    Sparkth itself only verifies tokens — the XBlock is what mints them in production. This
    lives here so the verification path has something to verify under test, and so both halves
    of the format are defined in one place.

    ``ttl`` defaults to the configured lifetime, resolved per call rather than as an argument
    default so it is not frozen at import time.
    """
    if ttl is None:
        ttl = get_pxc_settings().launch_token_ttl_seconds
    claims = {
        "act": activity,
        "plc": placement,
        "cid": course_id,
        "uid": user_id,
        "prm": permission,
        "exp": int(time()) + ttl,
    }
    payload = _b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    return f"{payload}.{_sign(payload, secret)}"


def read_launch_token(token: str) -> LaunchClaims:
    """Verify ``token`` against the configured secret and return its claims.

    The signature comparison runs through ``hmac.compare_digest`` for timing-safety. No test in
    this suite can observe timing, so that property is carried by this implementation and this
    docstring alone — not by a test.

    A bad signature is logged at ``warning`` level with a best-effort, explicitly unverified
    activity/placement hint (see ``_unverified_claims_hint``) — the most likely production cause
    is a shared-secret mismatch between Sparkth and the XBlock, which otherwise leaves an
    operator with nothing but learner-reported 401s.

    Raises:
        PxcInvalidLaunchToken: if no secret is configured, or the token is malformed, wrongly
            signed, or expired.
    """
    secret = get_pxc_settings().launch_secret
    if not secret:
        logger.error("PXC_LAUNCH_SECRET is not configured; refusing every launch token")
        raise PxcInvalidLaunchToken("Launch tokens are not configured")

    payload, _, signature = token.partition(".")
    if not payload or not signature:
        raise PxcInvalidLaunchToken("Malformed launch token")

    # Compare as bytes: str.encode() cannot fail, but hmac.compare_digest raises TypeError on a
    # str containing non-ASCII characters, and the signature is attacker-controlled.
    if not hmac.compare_digest(signature.encode(), _sign(payload, secret).encode()):
        logger.warning("Bad launch token signature%s", _unverified_claims_hint(payload))
        raise PxcInvalidLaunchToken("Bad launch token signature")

    try:
        claims = json.loads(_b64decode(payload))
    except (ValueError, UnicodeDecodeError) as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err

    try:
        if int(claims["exp"]) < int(time()):
            raise PxcInvalidLaunchToken("Expired launch token")
        activity, placement = str(claims["act"]), str(claims["plc"])
        return LaunchClaims(
            activity,
            placement,
            str(claims["cid"]),
            str(claims["uid"]),
            _read_permission(claims.get("prm"), activity, placement),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err
