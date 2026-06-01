import re
from pathlib import Path

# Slack OAuth endpoints
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Bot user-facing error and status messages
NO_AI_KEY_MESSAGE = "I'm not configured with an AI key yet. Please ask your instructor to add one in the bot settings."
AI_KEY_UNAVAILABLE_MESSAGE = "I couldn't connect to the AI service right now. Please try again in a moment."
NO_FILES_RESOLVED_MESSAGE = (
    "I don't have any documents available to answer that. "
    "Please ask your instructor to add documents to my reference list."
)
RAG_NOT_READY_MESSAGE = "I'm still indexing the course documents. Please try again in a few minutes."
DRIVE_FILE_NOT_FOUND_MESSAGE = (
    "I couldn't access one of my reference documents. Please ask your instructor to check the bot's configured sources."
)
RETRIEVAL_ERROR_MESSAGE = "Something went wrong while looking that up. Please try again in a moment."

# Greeting detection pattern
GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey(\s+there)?|howdy|greetings|sup|yo|hiya|good\s+(morning|afternoon|evening))[^\w]*\s*$",
    re.IGNORECASE,
)

# LLM synthesis system prompt
SYNTHESIS_SYSTEM_PROMPT = (Path(__file__).parent / "assets" / "synthesis_system_prompt.txt").read_text()
