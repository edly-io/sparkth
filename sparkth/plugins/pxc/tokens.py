"""The launch token: how a learner's identity reaches Sparkth from Open edX.

The XBlock mints a short-lived HS256 JWT carrying the Open edX user id, course id and
activity instance, signed with a secret shared between the two servers; this plugin verifies the
signature and takes the learner's identity from the token, so it never looks up a
learner itself. The one token Sparkth mints is an author's preview of their own activity
(``mint_preview_token``). The secret stays server-side at both ends and only the token travels through the
browser, which is what makes the identity trustworthy rather than client-asserted.

The claim names are the plugin's own — ``act``, ``ins``, ``cid``, ``uid`` — since none of the
registered JWT claims describe an activity instance or an activity type. Only ``exp`` is standard, and
it is PyJWT that enforces it.

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

from dataclasses import dataclass
from time import time
from uuid import UUID

import jwt
from pxc.lib.permission import Permission

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID, PXC_PREVIEW_USER_PREFIX
from sparkth.plugins.pxc.enums import PreviewPermission
from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken, PxcLaunchNotConfigured

logger = get_logger(__name__)

# Pinned on both halves of the token. Passing it to jwt.decode is what refuses a token whose
# header asks for `none`, or for an asymmetric algorithm that would verify against the shared
# secret as a public key.
LAUNCH_TOKEN_ALGORITHM = "HS256"


@dataclass(frozen=True)
class LaunchClaims:
    """Who is asking, for which activity instance of which activity, and at what permission."""

    activity: str
    activity_instance: str
    course_id: str
    user_id: str
    permission: Permission


def _unverified_claims_hint(token: str) -> str:
    """A best-effort ``" (unverified activity=..., activity_instance=...)"`` suffix for a log message.

    Called only after the signature check has already failed, so ``token`` is not proven genuine
    — a forged one can put anything here. Never used to authenticate anything, only to give an
    operator a diagnostic hint (e.g. spotting a shared-secret mismatch, where the token is
    genuine and only the signature side disagrees). Returns "" if the payload cannot be decoded,
    or decodes to something with no activity or activity instance to show.
    """
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return ""
    activity, activity_instance = claims.get("act"), claims.get("ins")
    if activity is None and activity_instance is None:
        return ""
    return " (unverified activity=%s, activity_instance=%s)" % (activity, activity_instance)


def _read_permission(value: object, activity: str, activity_instance: str) -> Permission:
    """The permission a verified token asks for, degrading to ``play`` when it names none.

    Absent means an XBlock older than the claim; unrecognised means version skew or a bug,
    since the claim sits inside the signed payload. Both take the least privilege rather than
    failing an otherwise legitimate launch. ``activity``/``activity_instance`` are logged alongside an
    unrecognised value so the warning can be correlated to a specific launch, the way
    ``_unverified_claims_hint`` already does for a bad signature.
    """
    if value is None:
        return Permission.play
    try:
        return Permission(str(value))
    except ValueError:
        logger.warning(
            "Launch token asked for unknown permission %r (activity=%s, activity_instance=%s); using play",
            value,
            activity,
            activity_instance,
        )
        return Permission.play


def mint_launch_token(
    activity: str,
    activity_instance: str,
    course_id: str,
    user_id: str,
    permission: str,
    secret: str,
    ttl: int | None = None,
) -> str:
    """Return a token carrying these claims, signed with ``secret`` and valid for ``ttl`` seconds.

    The XBlock mints LMS launches. Sparkth mints only an author's preview, through
    ``mint_preview_token``, and tests mint tokens to exercise verification. Both halves of the
    format are defined here.

    ``ttl`` defaults to the configured lifetime, resolved per call rather than as an argument
    default so it is not frozen at import time.
    """
    if ttl is None:
        ttl = get_pxc_settings().launch_token_ttl_seconds
    claims = {
        "act": activity,
        "ins": activity_instance,
        "cid": course_id,
        "uid": user_id,
        "prm": permission,
        "exp": int(time()) + ttl,
    }
    return jwt.encode(claims, secret, algorithm=LAUNCH_TOKEN_ALGORITHM)


def mint_preview_token(activity_id: UUID, user_id: int, permission: PreviewPermission) -> str:
    """A launch token for an author previewing their own generated activity inside Sparkth.

    The preview is the one launch Sparkth mints itself. It goes into a fixed preview course and
    activity instance, as a learner id namespaced away from Open edX's. The caller has already checked
    that the user owns the activity; the token only carries that decision to the embed.

    Raises:
        PxcLaunchNotConfigured: if ``PXC_LAUNCH_SECRET`` is empty, since PyJWT refuses an empty key.
    """
    secret = get_pxc_settings().launch_secret
    if not secret:
        logger.error("PXC_LAUNCH_SECRET is not configured; cannot mint a preview token for %s", activity_id)
        raise PxcLaunchNotConfigured("Activity previews are not configured on this server")
    return mint_launch_token(
        str(activity_id),
        PXC_PREVIEW_ACTIVITY_INSTANCE,
        PXC_PREVIEW_COURSE_ID,
        f"{PXC_PREVIEW_USER_PREFIX}{user_id}",
        permission,
        secret,
    )


def read_launch_token(token: str) -> LaunchClaims:
    """Verify ``token`` against the configured secret and return its claims.

    ``exp`` is required, not merely honoured when present: a launch token without one would be a
    permanent credential sitting in a URL.

    A bad signature is logged at ``warning`` level with a best-effort, explicitly unverified
    activity and activity instance hint (see ``_unverified_claims_hint``) — the most likely production cause
    is a shared-secret mismatch between Sparkth and the XBlock, which otherwise leaves an
    operator with nothing but learner-reported 401s.

    ``OverflowError`` is caught alongside PyJWT's own errors because it is the one malformed
    token PyJWT does not wrap: it coerces ``exp`` with ``int()``, and a JSON infinity makes that
    raise. Uncaught it would be a 500 where every other bad token is a 401.

    Raises:
        PxcInvalidLaunchToken: if no secret is configured, or the token is malformed, wrongly
            signed, or expired.
    """
    secret = get_pxc_settings().launch_secret
    if not secret:
        logger.error("PXC_LAUNCH_SECRET is not configured; refusing every launch token")
        raise PxcInvalidLaunchToken("Launch tokens are not configured")

    try:
        claims = jwt.decode(
            token,
            secret,
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
        activity, activity_instance = str(claims["act"]), str(claims["ins"])
        return LaunchClaims(
            activity,
            activity_instance,
            str(claims["cid"]),
            str(claims["uid"]),
            _read_permission(claims.get("prm"), activity, activity_instance),
        )
    except KeyError as err:
        raise PxcInvalidLaunchToken("Malformed launch token") from err
