"""Configuration and limits for Inkgauge."""

import os
from typing import Final

MAX_CHARACTERS: Final[int] = 150_000
READING_SPEED_WPM: Final[int] = 238

# Rate limits
RATE_LIMIT_CORE_PER_MINUTE: Final[int] = 30
RATE_LIMIT_AI_PER_HOUR: Final[int] = 30  # generous limit for local/free AI

# AI Models & Providers
ANTHROPIC_API_KEY: Final[str] = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_FAST_MODEL: Final[str] = os.getenv("INKGAUGE_FAST_MODEL", "claude-haiku-5-5")
DEFAULT_DEEP_MODEL: Final[str] = os.getenv("INKGAUGE_DEEP_MODEL", "claude-sonnet-5-5")

# Free Google Gemini API support
GEMINI_API_KEY: Final[str] = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: Final[str] = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Free Local Ollama support
OLLAMA_HOST: Final[str] = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL: Final[str] = os.getenv("OLLAMA_MODEL", "llama3.2")

FAST_MODEL_TIMEOUT_SECONDS: Final[float] = 20.0
DEEP_MODEL_TIMEOUT_SECONDS: Final[float] = 45.0
CACHE_TTL_SECONDS: Final[int] = 3600  # 1 hour
CHAPTER_READ_MAX_WORDS: Final[int] = 12_000
