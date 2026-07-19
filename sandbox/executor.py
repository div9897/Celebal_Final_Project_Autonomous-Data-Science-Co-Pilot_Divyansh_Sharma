"""
executor.py
-----------
Phase 4: sandboxed execution of LLM-generated code.

Why this exists: agent.py's run_generated_code() (Phase 3) uses exec() in
the SAME process as the Streamlit app. That's fine for a quick demo, but
it means LLM-written code could do anything your app's Python process can
do (read files, make network calls, etc). This module fixes that by:

1. Running the code in a completely separate subprocess (not the app's process)
2. Blocking dangerous imports (os, sys, subprocess, socket, shutil, etc.)
   via a restricted `__import__`
3. Enforcing a timeout, so a runaway/infinite loop can't hang the app
4. Communicating results back via files (a PNG for the chart, a JSON for
   insights) since you can't pass a live Python object across a process
   boundary

This is a defense-in-depth sandbox for a student/demo project — not a
substitute for a production-grade isolation layer (gVisor, Docker, Firecracker,
etc.), which would be the real answer at enterprise scale. That distinction is
worth mentioning in your final report/demo.
"""

import subprocess
import tempfile
import os
import sys
import json
import textwrap
import pandas as pd

# Modules the generated code is NOT allowed to import.
BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "requests", "urllib", "http", "ftplib", "smtplib",
    "multiprocessing", "threading", "ctypes",
}

TIMEOUT_SECONDS = 15

# This is the template for the child script that actually runs in the
# subprocess. It sets up a restricted import hook, loads the DataFrame
# from a CSV (safer + simpler than pickling across the process boundary),
# execs the LLM's code, then writes results to disk for the parent to read.
_RUNNER_TEMPLATE = '''
import builtins
import json
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless backend, no display needed in subprocess
import matplotlib.pyplot as plt

BLOCKED_MODULES = {blocked!r}

_real_import = builtins.__import__
def _restricted_import(name, globals=None, *args, **kwargs):
    top_level = name.split(".")[0]
    # Only block the import if it was triggered by the USER'S exec'd code
    # (identified by our sentinel key), not by pandas/matplotlib/numpy
    # internals doing their own legitimate imports behind the scenes.
    is_user_code = bool(globals) and globals.get("__sandbox_user_code__")
    if is_user_code and top_level in BLOCKED_MODULES:
        raise ImportError(f"Import of '{{name}}' is blocked in the sandbox.")
    return _real_import(name, globals, *args, **kwargs)
builtins.__import__ = _restricted_import

# IMPORTANT: this snapshot must be taken AFTER the line above, so that the
# "__import__" entry captured here is our restricted version, not the
# original. If taken before, exec'd code would silently use the original
# unrestricted __import__ via its own __builtins__ dict, defeating the hook.
SAFE_BUILTINS = {{k: v for k, v in vars(builtins).items() if k not in ("eval", "compile", "open", "__import__")}}
SAFE_BUILTINS["__import__"] = _restricted_import

df = pd.read_csv(r"{csv_path}")

user_code = {code!r}

result = {{"insights": []}}
try:
    user_globals = {{"__builtins__": SAFE_BUILTINS, "__sandbox_user_code__": True}}
    local_ns = {{"df": df, "pd": pd, "np": np, "plt": plt}}
    exec(user_code, user_globals, local_ns)

    fig = local_ns.get("fig")
    if fig is not None:
        fig.savefig(r"{png_path}", bbox_inches="tight", dpi=120)

    result["insights"] = local_ns.get("insights", [])
    result["success"] = True
    result["error"] = None

except Exception as e:
    result["success"] = False
    result["error"] = f"{{type(e).__name__}}: {{e}}"

with open(r"{result_path}", "w") as f:
    json.dump(result, f)
'''


def run_in_sandbox(code: str, df: pd.DataFrame) -> dict:
    """
    Execute LLM-generated code in an isolated subprocess.

    Returns a dict with keys:
        success: bool
        image_bytes: bytes or None (PNG data, if a chart was produced)
        insights: list[str]
        error: str or None
        stdout / stderr: str (raw subprocess output, useful for debugging)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "data.csv")
        png_path = os.path.join(tmpdir, "output.png")
        result_path = os.path.join(tmpdir, "result.json")
        script_path = os.path.join(tmpdir, "runner.py")

        df.to_csv(csv_path, index=False)

        script = _RUNNER_TEMPLATE.format(
            blocked=BLOCKED_MODULES,
            csv_path=csv_path,
            code=code,
            png_path=png_path,
            result_path=result_path,
        )
        with open(script_path, "w") as f:
            f.write(script)

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=tmpdir,  # confine the subprocess's working directory
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "image_bytes": None,
                "insights": [],
                "error": f"Code timed out after {TIMEOUT_SECONDS}s (possible infinite loop).",
                "stdout": "",
                "stderr": "",
            }

        # Read back structured result written by the child process
        if os.path.exists(result_path):
            with open(result_path) as f:
                result = json.load(f)
        else:
            # Child crashed before writing result.json (e.g. syntax error
            # in the sandbox script itself, or a blocked import at parse time)
            result = {
                "success": False,
                "error": proc.stderr.strip() or "Unknown sandbox failure.",
                "insights": [],
            }

        image_bytes = None
        if os.path.exists(png_path):
            with open(png_path, "rb") as f:
                image_bytes = f.read()

        return {
            "success": result.get("success", False),
            "image_bytes": image_bytes,
            "insights": result.get("insights", []),
            "error": result.get("error"),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
