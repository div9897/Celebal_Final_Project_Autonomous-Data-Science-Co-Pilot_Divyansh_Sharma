"""
agent.py
--------
Phase 3: the core "agent" logic.

Given a DataFrame's schema + a plain-English question, ask the LLM to
write executable pandas/matplotlib code, then run it.

IMPORTANT — this file's execution is NOT yet sandboxed (that's Phase 4).
Right now it uses a restricted exec() namespace, which is fine for local
development and demoing to yourself, but should NOT be treated as safe
against genuinely malicious code. Phase 4 replaces `run_generated_code`
with a subprocess-isolated version.
"""

import re
import io
import os
import sys
import contextlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from llm_client import ask_llm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from retriever import retrieve, format_for_prompt

SYSTEM_INSTRUCTION = """You are a data analysis assistant that writes Python/pandas code.

Rules you MUST follow:
1. Assume a pandas DataFrame named `df` is already loaded in the execution scope.
2. Do NOT read any file, do NOT redefine `df` from scratch, and do NOT import pandas/numpy/matplotlib — they're already available as pd, np, plt.
3. If the question calls for a chart, create it with matplotlib and store the Figure object in a variable called `fig`.
4. Store 2-4 short natural-language observations as a Python list of strings in a variable called `insights`.
5. Output ONLY a single Python code block. No explanations, no markdown outside the code block, no commentary before or after.
6. Keep the code short and directly focused on answering the question.
"""


def _build_prompt(schema_summary: str, question: str, previous_error: str | None = None) -> tuple[str, list[dict]]:
    """Construct the prompt sent to the LLM, including the schema and the
    user's question. If a previous attempt failed, include the error AND
    relevant documentation retrieved via RAG, so the model corrects itself
    grounded in real docs rather than guessing from memory alone.

    Returns (prompt, retrieved_chunks) -- chunks are returned separately so
    the caller can display what was retrieved, for transparency/demo purposes.
    """
    prompt = f"DataFrame schema:\n{schema_summary}\n\nUser question: {question}\n"
    retrieved_chunks = []

    if previous_error:
        prompt += (
            f"\nYour previous code raised this error:\n{previous_error}\n"
            "Fix the code so it runs without error, and still answers the question."
        )

        # RAG step: retrieve docs relevant to this specific error and
        # ground the fix in them instead of relying purely on the LLM's
        # own (possibly stale) training knowledge.
        try:
            retrieved_chunks = retrieve(previous_error, top_k=2)
            docs_block = format_for_prompt(retrieved_chunks)
            if docs_block:
                prompt += f"\n\n{docs_block}\n"
        except FileNotFoundError:
            # Index not built yet -- self-correction still works, just
            # without the RAG grounding. See rag/build_index.py.
            pass

    return prompt, retrieved_chunks


def _extract_code(llm_response: str) -> str:
    """Pull code out of a ```python ... ``` block. Falls back to the raw
    response if no fenced block is found (some models omit the fence)."""
    match = re.search(r"```(?:python)?\s*(.*?)```", llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response.strip()


def generate_code(schema_summary: str, question: str, previous_error: str | None = None) -> tuple[str, list[dict]]:
    """Ask the LLM to write pandas/matplotlib code for the given question.

    Returns (code, retrieved_docs) -- retrieved_docs is empty on a first
    attempt (no error yet to look up) and populated on retries once RAG
    has grounded the fix in relevant documentation.
    """
    prompt, retrieved_chunks = _build_prompt(schema_summary, question, previous_error)
    response = ask_llm(prompt, system_instruction=SYSTEM_INSTRUCTION, temperature=0.2)
    return _extract_code(response), retrieved_chunks


def run_generated_code(code: str, df: pd.DataFrame) -> dict:
    """
    Execute LLM-generated code against the given DataFrame.

    Returns a dict with keys:
        success: bool
        fig: matplotlib Figure or None
        insights: list[str]
        error: str or None (traceback-like message if it failed)
        stdout: captured print() output, if any
    """
    plt.close("all")  # avoid leaking figures between runs

    # Restricted-ish namespace: only what the agent should need.
    # NOTE: this is NOT a real security sandbox — see Phase 4.
    local_ns = {"df": df.copy(), "pd": pd, "np": np, "plt": plt}
    stdout_buffer = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_buffer):
            exec(code, {"__builtins__": __builtins__}, local_ns)

        return {
            "success": True,
            "fig": local_ns.get("fig"),
            "insights": local_ns.get("insights", []),
            "error": None,
            "stdout": stdout_buffer.getvalue(),
        }

    except Exception as e:
        return {
            "success": False,
            "fig": None,
            "insights": [],
            "error": f"{type(e).__name__}: {e}",
            "stdout": stdout_buffer.getvalue(),
        }
