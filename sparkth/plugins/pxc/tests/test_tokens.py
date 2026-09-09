import logging
import time

import pytest

from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken
from sparkth.plugins.pxc.tokens import (
    LaunchClaims,
    _b64encode,
    _sign,
    mint_launch_token,
    read_launch_token,
)

CLAIMS = ("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_a_minted_token_reads_back_its_claims(configured_secret: str) -> None:

    claims = read_launch_token(mint_launch_token(*CLAIMS, configured_secret, 300))

    assert claims == LaunchClaims("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_a_token_signed_with_another_secret_is_refused(configured_secret: str) -> None:

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token(mint_launch_token(*CLAIMS, "a-different-secret", 300))


def test_a_signature_mismatch_is_logged_with_the_claimed_activity_and_placement(
    configured_secret: str, caplog: pytest.LogCaptureFixture
) -> None:
    # A secret mismatch between Sparkth and the XBlock — the most likely production failure per
    # xblock/README.md — produces a genuine token signed with the wrong secret. Before this,
    # read_launch_token logged only the unconfigured-secret case, so an operator saw learners
    # failing with 401s and had no server-side trace of why.
    token = mint_launch_token(*CLAIMS, "a-different-secret", 300)

    with caplog.at_level(logging.WARNING, logger="sparkth.plugins.pxc.tokens"):
        with pytest.raises(PxcInvalidLaunchToken, match="signature"):
            read_launch_token(token)

    assert "mcq" in caplog.text
    assert "placement-1" in caplog.text
    # Never the secret or any part of the token itself.
    assert configured_secret not in caplog.text
    assert token not in caplog.text


def test_a_signature_mismatch_with_an_undecodable_payload_is_still_logged(
    configured_secret: str, caplog: pytest.LogCaptureFixture
) -> None:
    # The claims hint is best-effort: a payload that cannot even be decoded (as opposed to one
    # that decodes but was never genuine) must not blow up the warning it is attached to.

    with caplog.at_level(logging.WARNING, logger="sparkth.plugins.pxc.tokens"):
        with pytest.raises(PxcInvalidLaunchToken, match="signature"):
            read_launch_token("not-valid-base64-json.wrong-signature")

    assert "signature" in caplog.text


def test_a_tampered_payload_is_refused(configured_secret: str) -> None:
    payload, signature = mint_launch_token(*CLAIMS, configured_secret, 300).split(".")
    forged = mint_launch_token("mcq", "placement-2", "course-v1:X+Y+Z", "learner-7", configured_secret, 300)

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token(f"{forged.split('.')[0]}.{signature}")


def test_an_expired_token_is_refused(configured_secret: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", lambda: time.time() - 3600)
    expired = mint_launch_token(*CLAIMS, configured_secret, 300)
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", time.time)

    with pytest.raises(PxcInvalidLaunchToken, match="Expired"):
        read_launch_token(expired)


def test_a_malformed_token_is_refused(configured_secret: str) -> None:

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token("not-a-token")


def test_verification_without_a_configured_secret_is_refused() -> None:
    with pytest.raises(PxcInvalidLaunchToken, match="not configured"):
        read_launch_token(mint_launch_token(*CLAIMS, "any-secret", 300))


def test_a_non_ascii_signature_is_refused_not_raised_as_a_type_error(configured_secret: str) -> None:

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token("abc.é")


def test_the_signature_is_checked_before_the_payload_is_decoded(configured_secret: str) -> None:

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token("not-valid-base64-json.wrong-signature")


def test_an_exp_that_overflows_to_infinity_is_refused(configured_secret: str) -> None:
    payload = _b64encode(b'{"act":"mcq","plc":"placement-1","cid":"course-v1:X+Y+Z","uid":"learner-7","exp":1e400}')
    token = f"{payload}.{_sign(payload, configured_secret)}"

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token(token)
