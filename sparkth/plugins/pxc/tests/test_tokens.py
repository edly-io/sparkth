import logging
import time

import jwt
import pytest

from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken
from sparkth.plugins.pxc.tokens import LaunchClaims, mint_launch_token, read_launch_token

SECRET = "a-shared-secret-of-at-least-32-bytes"
CLAIMS = ("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_a_minted_token_reads_back_its_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    claims = read_launch_token(mint_launch_token(*CLAIMS, SECRET, 300))

    assert claims == LaunchClaims("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_a_token_signed_with_another_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token(mint_launch_token(*CLAIMS, "a-different-secret-of-32-plus-bytes", 300))


def test_a_signature_mismatch_is_logged_with_the_claimed_activity_and_placement(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # A secret mismatch between Sparkth and the XBlock — the most likely production failure per
    # the XBlock's README — produces a genuine token signed with the wrong secret. Without the hint,
    # an operator sees learners failing with 401s and has no server-side trace of why.
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    token = mint_launch_token(*CLAIMS, "a-different-secret-of-32-plus-bytes", 300)

    with caplog.at_level(logging.WARNING, logger="sparkth.plugins.pxc.tokens"):
        with pytest.raises(PxcInvalidLaunchToken, match="signature"):
            read_launch_token(token)

    assert "mcq" in caplog.text
    assert "placement-1" in caplog.text
    # Never the secret or any part of the token itself.
    assert SECRET not in caplog.text
    assert token not in caplog.text


def test_a_signature_mismatch_with_an_undecodable_payload_is_still_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # The claims hint is best-effort: a payload that cannot be decoded at all must not blow up
    # the warning it is attached to. Corrupting the payload segment leaves the signature to fail
    # first, which is the branch that asks for the hint.
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    header, _, signature = mint_launch_token(*CLAIMS, SECRET, 300).split(".")

    with caplog.at_level(logging.WARNING, logger="sparkth.plugins.pxc.tokens"):
        with pytest.raises(PxcInvalidLaunchToken, match="signature"):
            read_launch_token(f"{header}.!!not-base64!!.{signature}")

    # Exactly the bare message: the hint contributed nothing rather than raising. A substring
    # check would pass either way, since the prefix is there regardless of what the hint did.
    assert caplog.messages == ["Bad launch token signature"]


def test_a_tampered_payload_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # Distinct from the wrong-secret case above: both segments here were signed with the real
    # secret, just not together. This is what stops a learner swapping in another placement's
    # payload from a token they legitimately hold.
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    header, _, signature = mint_launch_token(*CLAIMS, SECRET, 300).split(".")
    forged = mint_launch_token("mcq", "placement-2", "course-v1:X+Y+Z", "learner-7", SECRET, 300)

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token(f"{header}.{forged.split('.')[1]}.{signature}")


def test_an_expired_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patches the clock the token is minted under, not the one it is verified under: expiry is
    # checked by PyJWT against the real clock, so an hour-old mint is genuinely past its ttl.
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", lambda: time.time() - 3600)
    expired = mint_launch_token(*CLAIMS, SECRET, 300)
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", time.time)

    with pytest.raises(PxcInvalidLaunchToken, match="Expired"):
        read_launch_token(expired)


def test_a_token_without_an_expiry_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # A token that never expires is a permanent launch credential in a URL, so an absent `exp`
    # is refused rather than treated as "no deadline".
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    token = jwt.encode({"act": "mcq", "plc": "p1", "cid": "c", "uid": "u"}, SECRET, algorithm="HS256")

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token(token)


def test_a_token_asking_for_the_none_algorithm_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # `alg: none` is the standing JWT attack: the header asks the verifier to skip the signature
    # entirely. Refused because the decode pins the accepted algorithms to HS256.
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    unsigned = jwt.encode(
        {"act": "mcq", "plc": "p1", "cid": "c", "uid": "u", "exp": int(time.time()) + 300},
        key="",
        algorithm="none",
    )

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token(unsigned)


def test_a_malformed_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token("not-a-token")


def test_verification_without_a_configured_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", "")

    with pytest.raises(PxcInvalidLaunchToken, match="not configured"):
        read_launch_token(mint_launch_token(*CLAIMS, SECRET, 300))


def test_a_non_ascii_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token("abc.é.def")


def test_an_exp_that_overflows_to_infinity_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # PyJWT coerces `exp` with `int()`, which raises OverflowError — not an InvalidTokenError —
    # on a JSON infinity. Uncaught, that is a 500 where every other bad token is a 401.
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    token = jwt.encode({"act": "mcq", "plc": "p1", "cid": "c", "uid": "u", "exp": 1e400}, SECRET, algorithm="HS256")

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token(token)


def test_a_token_missing_a_claim_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    token = jwt.encode({"act": "mcq", "exp": int(time.time()) + 300}, SECRET, algorithm="HS256")

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token(token)
