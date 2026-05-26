"""
OpenAI API wrapper with structured JSON and plain text modes.

Provides two calling patterns:
- chat_json: Forces JSON response format for structured data extraction
- chat_text: Plain text responses for classification tasks

Uses response_format={"type": "json_object"} for reliable JSON parsing.
"""
import json
import logging
import os
from typing import Optional

import openai

logger = logging.getLogger(__name__)

_client: Optional[openai.OpenAI] = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = openai.OpenAI(api_key=api_key)
    return _client


def _get_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def chat_json(prompt: str, temperature: float = 0.2) -> dict | None:
    """
    Send a prompt and parse the response as JSON.

    Uses response_format=json_object to guarantee valid JSON output.
    Returns parsed dict or None on failure.
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
        logger.error("OpenAI JSON error: %s", e)
        return None


def chat_text(prompt: str, temperature: float = 0.1, max_tokens: int = 100) -> str | None:
    """
    Send a prompt and return the response as cleaned text.

    Strips surrounding quotes for classification-style responses.
    Returns cleaned string or None on failure.
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
        logger.error("OpenAI text error: %s", e)
        return None
