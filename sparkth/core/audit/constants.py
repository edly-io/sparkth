"""Constants for the audit subsystem.

Internal to :mod:`sparkth.core.audit`; nothing here is re-exported through the
:mod:`sparkth.lib.audit` public surface.
"""

from sparkth.core.audit.types import AnonymousActor

REDACTED = "[REDACTED]"

# Containers nested deeper than this are replaced with REDACTED wholesale.
# Payloads are attacker-influenceable (LLM/plugin-generated tool args), and an
# unbounded recursive walk would hit the interpreter recursion limit around
# depth ~500, far below what json.loads accepts. Real payloads are a few
# levels deep; replacing (rather than raising) guarantees nothing unscanned
# is ever persisted while keeping the audited action alive.
MAX_DEPTH = 64

# Keys whose value is replaced wholesale, matched case-insensitively at any depth.
# "auth" covers the credential sub-objects plugins nest into tool args.
SECRET_KEYS = frozenset(
    {
        "auth",
        "authorization",
        "password",
        "passwd",
        "secret",
        "client_secret",
        "token",
        "api_token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "private_key",
    }
)

# Default actor recorded when neither the event nor the context names one.
ANONYMOUS_ACTOR = AnonymousActor()

# Target type carried by the tool.invoked / tool.completed / tool.failed pair.
# Both events of one execution share a generated target id, so an invocation
# whose process crashed mid-execution is detectable as an invoked event with
# no matching outcome event.
TOOL_INVOCATION_TARGET_TYPE = "tool_invocation"
