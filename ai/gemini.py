"""
ai/gemini.py — Gemini API client using the new google-genai SDK.
"""

import json
import time

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_SUMMARY_MODEL,
    GEMINI_REASONING_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MAX_RETRIES,
    GEMINI_BACKOFF_BASE,
)

_client = None


def _get_client():
    global _client

    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY not found. Please add it to your .env file."
            )

        _client = genai.Client(api_key=GEMINI_API_KEY)

    return _client


def call_gemini(
    prompt: str,
    use_reasoning: bool = False,
    json_output: bool = False,
) -> str:
    client = _get_client()

    model_name = (
        GEMINI_REASONING_MODEL
        if use_reasoning
        else GEMINI_SUMMARY_MODEL
    )

    if json_output:
        config = types.GenerateContentConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
        )
    else:
        config = types.GenerateContentConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
        )

    last_error = None

    for attempt in range(GEMINI_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )

            if not response.text:
                raise RuntimeError("Gemini returned an empty response.")

            return response.text

        except Exception as e:
            error = str(e).lower()
            last_error = e

            if any(
                x in error
                for x in [
                    "429",
                    "503",
                    "resource_exhausted",
                    "quota",
                    "rate",
                    "unavailable",
                ]
            ):
                wait = GEMINI_BACKOFF_BASE ** (attempt + 1)
                time.sleep(wait)
                continue

            raise RuntimeError(f"Gemini API error:\n{e}") from e

    raise RuntimeError(
        f"Gemini failed after {GEMINI_MAX_RETRIES} retries.\n"
        f"Last error:\n{last_error}"
    )


def call_gemini_json(prompt: str, use_reasoning: bool = False):
    """
    Calls Gemini and returns parsed JSON.
    """

    raw = call_gemini(
        prompt,
        use_reasoning=use_reasoning,
        json_output=True,
    )

    cleaned = raw.strip()

    # Remove markdown code fences if Gemini returns them
    if cleaned.startswith("```"):

        lines = cleaned.splitlines()

        lines = [
            line
            for line in lines
            if not line.strip().startswith("```")
        ]

        cleaned = "\n".join(lines).strip()

    try:

        return json.loads(cleaned)

    except json.JSONDecodeError as e:

        print("\n========= RAW GEMINI RESPONSE =========")
        print(raw)
        print("=======================================\n")

        raise RuntimeError(
            f"Gemini returned invalid JSON.\n\n"
            f"{e}\n\n"
            f"Raw response:\n{raw}"
        ) from e