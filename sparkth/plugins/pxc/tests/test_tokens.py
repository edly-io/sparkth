import time

import pytest

from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken
from sparkth.plugins.pxc.tokens import LaunchClaims, mint_launch_token, read_launch_token

SECRET = "shared-secret"
CLAIMS = ("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_a_minted_token_reads_back_its_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    claims = read_launch_token(mint_launch_token(*CLAIMS, SECRET, 300))

    assert claims == LaunchClaims("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_a_token_signed_with_another_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token(mint_launch_token(*CLAIMS, "a-different-secret", 300))


def test_a_tampered_payload_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    payload, signature = mint_launch_token(*CLAIMS, SECRET, 300).split(".")
    forged = mint_launch_token("mcq", "placement-2", "course-v1:X+Y+Z", "learner-7", SECRET, 300)

    with pytest.raises(PxcInvalidLaunchToken, match="signature"):
        read_launch_token(f"{forged.split('.')[0]}.{signature}")


def test_an_expired_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", lambda: time.time() - 3600)
    expired = mint_launch_token(*CLAIMS, SECRET, 300)
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", time.time)

    with pytest.raises(PxcInvalidLaunchToken, match="Expired"):
        read_launch_token(expired)


def test_a_malformed_token_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)

    with pytest.raises(PxcInvalidLaunchToken, match="Malformed"):
        read_launch_token("not-a-token")


def test_verification_without_a_configured_secret_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", "")

    with pytest.raises(PxcInvalidLaunchToken, match="not configured"):
        read_launch_token(mint_launch_token(*CLAIMS, SECRET, 300))
