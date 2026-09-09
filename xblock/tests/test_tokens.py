"""Tests pinning the launch token's wire format against Sparkth's verifier.

``sparkth/plugins/pxc/tokens.py`` verifies the tokens minted here; the two packages cannot
import each other (separate distributions on separate servers), so these assertions are the
contract that keeps them in sync. If either side's claim names or signing scheme change, this
test and the verifier's own tests must change together.
"""

import json
from base64 import urlsafe_b64decode

from sparkth_pxc.tokens import mint_launch_token


def test_the_token_carries_the_documented_claim_names() -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "edit", "s", 300)
    payload = token.split(".")[0]
    claims = json.loads(urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))

    assert set(claims) == {"act", "plc", "cid", "uid", "prm", "exp"}
    assert claims["act"] == "mcq"
    assert claims["plc"] == "placement-1"
    assert claims["cid"] == "course-v1:X+Y+Z"
    assert claims["uid"] == "learner-7"
    assert claims["prm"] == "edit"


def test_the_payload_is_signed_with_the_shared_secret() -> None:
    import hashlib
    import hmac
    from base64 import urlsafe_b64encode

    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", "s", 300)
    payload, signature = token.split(".")
    expected = urlsafe_b64encode(hmac.new(b"s", payload.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()

    assert signature == expected
