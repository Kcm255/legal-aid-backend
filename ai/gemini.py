"""Backward-compatible import shim for older integrations.

The application now uses the local/remote Ollama client in ``ai.llm``.
"""

from ai.llm import call_llm, call_llm_json


def call_gemini(prompt: str, use_reasoning: bool = False, json_output: bool = False) -> str:
    return call_llm(prompt, use_reasoning=use_reasoning, json_output=json_output)


def call_gemini_json(prompt: str, use_reasoning: bool = False) -> dict:
    return call_llm_json(prompt, use_reasoning=use_reasoning)
