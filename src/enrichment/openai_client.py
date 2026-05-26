"""
Reusable OpenAI wrapper with JSON and plain-text response modes.

Reads configuration from environment variables:
  OPENAI_API_KEY  - required
  OPENAI_MODEL    - optional, defaults to "gpt-4o-mini"
"""
import json
import logging
import os
from typing import Optional

import openai

logger = logging.getLogger(__name__)

_client: Optional[openai.OpenAI] = None

DEFAULT_MODEL = "gpt-4o-mini"


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")
        _client = openai.OpenAI(api_key=api_key)
    return _client


def _get_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def chat_json(prompt: str, temperature: float = 0.2) -> dict | None:
    """
    Send a prompt and expect a JSON response.
    Returns the parsed dict, or None on failure.
    """
    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model=_get_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logger.error("OpenAI JSON request failed: %s", e)
        return None


def chat_text(prompt: str, temperature: float = 0.1, max_tokens: int = 100) -> str | None:
    """
    Send a prompt and expect a plain-text response.
    Returns the cleaned string, or None on failure.
    """
    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model=_get_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content.strip().strip('"').strip("'")
    except Exception as e:
        logger.error("OpenAI text request failed: %s", e)
        return None
