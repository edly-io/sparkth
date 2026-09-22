"""Tests pinning the launch token's wire format against Sparkth's verifier.

``sparkth/plugins/pxc/tokens.py`` verifies the tokens minted here; the two packages cannot
import each other (separate distributions on separate servers), so these assertions are the
contract that keeps them in sync. PyJWT carries the signing and expiry, which leaves three
things that are still this project's own choice and would silently break a launch if either
side changed them alone: the claim names, the algorithm, and the presence of ``exp``.
"""

from time import time

import jwt
import pytest
from sparkth_pxc.tokens import mint_launch_token

SECRET = "a-shared-secret-of-at-least-32-bytes"


def test_the_token_carries_the_documented_claim_names() -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", SECRET, 300)

    claims = jwt.decode(token, SECRET, algorithms=["HS256"])

    assert set(claims) == {"act", "plc", "cid", "uid", "exp"}
    assert claims["act"] == "mcq"
    assert claims["plc"] == "placement-1"
    assert claims["cid"] == "course-v1:X+Y+Z"
    assert claims["uid"] == "learner-7"


def test_the_token_is_signed_with_hs256() -> None:
    # Sparkth's verifier pins `algorithms=["HS256"]`, so minting under any other algorithm
    # fails every launch rather than falling back.
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", SECRET, 300)

    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_a_token_does_not_verify_under_a_different_secret() -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", SECRET, 300)

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "a-different-secret-of-32-plus-bytes", algorithms=["HS256"])


def test_the_expiry_is_the_ttl_from_now() -> None:
    # Sparkth refuses a token with no `exp` outright, and expires it against its own clock, so
    # the claim has to be an absolute deadline rather than a duration.
    before = int(time())
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", SECRET, 300)

    exp = jwt.decode(token, SECRET, algorithms=["HS256"])["exp"]

    assert before + 300 <= exp <= int(time()) + 300
