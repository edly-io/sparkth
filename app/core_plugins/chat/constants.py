import os

# Conversation title generation
TITLE_PROMPT_MAX_CHARS: int = int(os.environ.get("CHAT_TITLE_PROMPT_MAX_CHARS", "500"))
TITLE_LLM_MAX_TOKENS: int = int(os.environ.get("CHAT_TITLE_LLM_MAX_TOKENS", "20"))
TITLE_DB_MAX_LENGTH: int = int(os.environ.get("CHAT_TITLE_DB_MAX_LENGTH", "255"))
TITLE_LLM_TEMPERATURE: float = float(os.environ.get("CHAT_TITLE_LLM_TEMPERATURE", "0.3"))

# RAG retrieval
DEFAULT_SIMILARITY_THRESHOLD: float = float(os.environ.get("CHAT_DEFAULT_SIMILARITY_THRESHOLD", "0.45"))
