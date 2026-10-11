"""Multi-provider AI client supporting Local Offline Engine, Google Gemini, Ollama, and Anthropic."""

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError
import httpx

import anthropic
from app.config import (
    ANTHROPIC_API_KEY,
    DEFAULT_FAST_MODEL,
    DEFAULT_DEEP_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    FAST_MODEL_TIMEOUT_SECONDS,
    DEEP_MODEL_TIMEOUT_SECONDS,
    CACHE_TTL_SECONDS,
)

logger = logging.getLogger("inkgauge.ai")

# In-memory response cache: hash -> (timestamp, response_dict)
_RESPONSE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _make_cache_key(*args: Any) -> str:
    """Compute sha256 cache key from input arguments."""
    serialized = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_cached_response(key: str) -> Optional[Dict[str, Any]]:
    """Retrieve response from cache if not expired."""
    if key in _RESPONSE_CACHE:
        timestamp, data = _RESPONSE_CACHE[key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return data
        else:
            del _RESPONSE_CACHE[key]
    return None


def _set_cached_response(key: str, data: Dict[str, Any]) -> None:
    """Save response to cache."""
    _RESPONSE_CACHE[key] = (time.time(), data)


def get_active_provider() -> str:
    """Determine the active AI provider based on configuration."""
    if ANTHROPIC_API_KEY.strip():
        return "anthropic"
    if GEMINI_API_KEY.strip():
        return "gemini"
    return "local"


def _clean_json_string(content_text: str) -> str:
    """Extract and sanitize JSON from markdown fenced blocks."""
    clean = content_text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean = "\n".join(lines).strip()
    return clean


def _call_gemini_json(
    system_prompt: str,
    user_prompt: str,
    timeout_secs: float,
) -> Optional[str]:
    """Call Google Gemini REST API."""
    if not GEMINI_API_KEY.strip():
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY.strip()}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"System instructions:\n{system_prompt}\n\nTask:\n{user_prompt}\n\nOutput ONLY valid JSON."}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        }
    }

    try:
        with httpx.Client(timeout=timeout_secs) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
    except Exception as e:
        logger.warning("Gemini API call failed: %s", e)
    return None


def _call_ollama_json(
    system_prompt: str,
    user_prompt: str,
    timeout_secs: float,
) -> Optional[str]:
    """Call local Ollama endpoint if running."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + "\n\nRespond ONLY with strict JSON."}
        ],
        "format": "json",
        "stream": False,
    }

    try:
        with httpx.Client(timeout=timeout_secs) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
    except Exception:
        # Ollama not running locally; silently fall back
        pass
    return None


def _call_anthropic_json(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    timeout_secs: float,
    max_tokens: int,
) -> Optional[str]:
    """Call Anthropic API."""
    if not ANTHROPIC_API_KEY.strip():
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY.strip())
        response = client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=timeout_secs,
        )
        if response.content and len(response.content) > 0:
            first_block = response.content[0]
            if hasattr(first_block, "text"):
                return first_block.text
    except Exception as e:
        logger.warning("Anthropic API call failed: %s", e)
    return None


def call_ai_json(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[BaseModel],
    model_type: str = "fast",
    max_tokens: int = 1024,
) -> Tuple[Optional[BaseModel], Optional[str], str]:
    """
    Call configured AI provider (Anthropic -> Gemini -> Ollama),
    validating with Pydantic. If all external providers fail or are unconfigured,
    signals caller to use built-in local engine.
    Returns: (validated_model, error_or_fallback_signal, provider_used)
    """
    model_name = DEFAULT_FAST_MODEL if model_type == "fast" else DEFAULT_DEEP_MODEL
    timeout_secs = FAST_MODEL_TIMEOUT_SECONDS if model_type == "fast" else DEEP_MODEL_TIMEOUT_SECONDS

    cache_key = _make_cache_key(model_name, system_prompt, user_prompt)
    cached = _get_cached_response(cache_key)
    if cached is not None:
        try:
            return response_model.model_validate(cached), None, "cached"
        except ValidationError:
            pass

    content_text = None
    provider_used = "local"

    # Try Anthropic if key provided
    if ANTHROPIC_API_KEY.strip():
        content_text = _call_anthropic_json(system_prompt, user_prompt, model_name, timeout_secs, max_tokens)
        if content_text:
            provider_used = "anthropic"

    # Try Gemini if key provided and Anthropic not used
    if not content_text and GEMINI_API_KEY.strip():
        content_text = _call_gemini_json(system_prompt, user_prompt, timeout_secs)
        if content_text:
            provider_used = "gemini"

    # Try Ollama if running
    if not content_text:
        content_text = _call_ollama_json(system_prompt, user_prompt, timeout_secs)
        if content_text:
            provider_used = "ollama"

    if content_text:
        try:
            clean_json = _clean_json_string(content_text)
            parsed = json.loads(clean_json)
            validated = response_model.model_validate(parsed)
            _set_cached_response(cache_key, parsed)
            return validated, None, provider_used
        except Exception as e:
            logger.warning("Failed to validate external model JSON (%s): %s", provider_used, e)

    # Fallback to local engine
    return None, "FALLBACK_TO_LOCAL", "local"
