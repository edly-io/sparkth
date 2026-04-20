import re

SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

BOT_SCOPES = [
    "app_mentions:read",
    "channels:history",
    "chat:write",
    "im:history",
    "im:read",
    "im:write",
]

STATE_MAX_AGE = 600  # 10 minutes

GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey(\s+there)?|howdy|greetings|sup|yo|hiya|good\s+(morning|afternoon|evening))[^\w]*\s*$",
    re.IGNORECASE,
)
