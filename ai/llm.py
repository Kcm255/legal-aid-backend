"""Local/remote Ollama LLM client used by summaries, chat, and translation."""

import json
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from config import (
    LLM_PROVIDER,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT,
    LLM_TEMPERATURE,
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MAX_RETRIES,
)


def _ollama_chat_url() -> str:
    """Resolve a host, OpenAI-compatible base, or native Ollama URL to /api/chat."""
    parsed = urlsplit(LLM_BASE_URL.rstrip("/"))
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("LLM_BASE_URL must be an absolute http(s) URL.")
    if parsed.path == "/api/chat":
        return LLM_BASE_URL.rstrip("/")
    root = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return f"{root}/api/chat"


def call_llm(prompt: str, use_reasoning: bool = False, json_output: bool = False) -> str:
    if LLM_PROVIDER != "ollama":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")
    del use_reasoning  # Qwen3 uses one configured model for both tasks.
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": LLM_TEMPERATURE,
            "num_predict": LLM_MAX_OUTPUT_TOKENS,
        },
    }
    if json_output:
        payload["format"] = "json"

    last_error = None
    attempts = max(1, LLM_MAX_RETRIES)
    for attempt in range(attempts):
        try:
            response = requests.post(
                _ollama_chat_url(),
                json=payload,
                timeout=LLM_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
            content = (body.get("message") or {}).get("content", "").strip()
            if not content:
                raise RuntimeError("Ollama returned an empty response.")
            return content
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        "The local Qwen server is unavailable or failed to answer. "
        f"Check Ollama, the SSH tunnel, and model '{LLM_MODEL}'. ({last_error})"
    ) from last_error


def call_llm_json(prompt: str, use_reasoning: bool = False) -> dict:
    raw = call_llm(prompt, use_reasoning=use_reasoning, json_output=True)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Qwen returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Qwen returned JSON, but it was not an object.")
    return parsed
