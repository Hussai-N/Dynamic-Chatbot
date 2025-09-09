import os

# Prefer environment variables; fall back to existing values for convenience
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBpQXS0jtOsTwDaLoSNmQZPw69zvJNCR8g")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # number of words per chunk

# Request/latency tuning
CONTEXT_MAX_CHARS = int(os.getenv("CONTEXT_MAX_CHARS", "12000"))  # cap website context to reduce latency
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))      # number of recent turns to include in prompt
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "90"))            # request timeout in seconds
