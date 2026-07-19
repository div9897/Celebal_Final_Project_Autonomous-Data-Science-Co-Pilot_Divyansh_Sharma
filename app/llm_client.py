"""
llm_client.py
--------------
Thin wrapper around the Gemini API (google-genai SDK).

Why this file exists:
Every other part of the app (code generation, self-correction, insight
summaries) calls `ask_llm(...)` instead of talking to Gemini directly.
That means if you ever swap providers (OpenAI, Claude, local model),
you only change THIS file — nothing else in the codebase needs to know
or care which LLM is behind it.
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()  # reads .env file into environment variables

_API_KEY = os.getenv("GEMINI_API_KEY")
_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

if not _API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Create a .env file (see .env.example) "
        "and put your key in it."
    )

# One client, reused across calls (avoids reconnecting every request)
_client = genai.Client(api_key=_API_KEY)


def ask_llm(prompt: str, system_instruction: str | None = None, temperature: float = 0.2) -> str:
    """
    Send a prompt to Gemini and return the plain text response.

    Args:
        prompt: the user-facing content (question, schema, error, etc.)
        system_instruction: role/behavior instructions for the model
        temperature: lower = more deterministic (good for code generation)

    Returns:
        The model's text response as a string.
    """
    config = {"temperature": temperature}
    if system_instruction:
        config["system_instruction"] = system_instruction

    response = _client.models.generate_content(
        model=_MODEL_NAME,
        contents=prompt,
        config=config,
    )
    return response.text


def test_connection() -> str:
    """Quick sanity check used by the Streamlit UI's 'Test Connection' button."""
    return ask_llm("Reply with exactly: Connection successful.")
