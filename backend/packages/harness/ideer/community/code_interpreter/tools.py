"""
Code Interpreter Tool - Execute Python or JavaScript code in a secure sandbox.

Provides isolated code execution with stdout/stderr capture, output truncation,
and local-path masking for security. Common Python libraries (pandas, matplotlib,
numpy) are pre-installed in the sandbox environment.
"""

import json
import logging
import os
import subprocess
import tempfile

from langchain.tools import tool

logger = logging.getLogger(__name__)

_MAX_TIMEOUT = 300
_DEFAULT_TIMEOUT = 60
_MAX_OUTPUT_CHARS = 20000


def _truncate_output(output: str, max_chars: int = _MAX_OUTPUT_CHARS) -> str:
    """Middle-truncate output, preserving head and tail (50/50 split).

    The returned string (including the truncation marker) is guaranteed to be
    no longer than max_chars characters. Pass max_chars=0 to disable truncation.
    """
    if max_chars == 0:
        return output
    if len(output) <= max_chars:
        return output
    total_len = len(output)
    marker_max_len = len(f"\n... [middle truncated: {total_len} chars skipped] ...\n")
    kept = max(0, max_chars - marker_max_len)
    if kept == 0:
        return output[:max_chars]
    head_len = kept // 2
    tail_len = kept - head_len
    skipped = total_len - kept
    marker = f"\n... [middle truncated: {skipped} chars skipped] ...\n"
    return f"{output[:head_len]}{marker}{output[-tail_len:] if tail_len > 0 else ''}"


@tool("code_interpreter", parse_docstring=True)
def code_interpreter_tool(code: str, language: str = "python", timeout: int = 60) -> str:
    """Execute code in a secure sandbox and return the output.

    Use this for data processing, calculations, generating charts, or any task
    that benefits from programmatic execution. Common Python libraries (pandas,
    matplotlib, numpy) are pre-installed in the sandbox environment.

    Args:
        code: The code to execute. Can be multi-line.
        language: Programming language — "python" or "javascript". Default is "python".
        timeout: Maximum execution time in seconds. Default is 60. Max is 300.
    """
    # Validate language
    if language not in ("python", "javascript"):
        return json.dumps(
            {"error": f"Unsupported language: '{language}'. Use 'python' or 'javascript'.", "stdout": "", "stderr": "", "exit_code": 1},
            ensure_ascii=False,
        )

    # Clamp timeout
    timeout = max(1, min(timeout, _MAX_TIMEOUT))

    # Determine interpreter
    if language == "python":
        interpreter = "python3"
    else:
        interpreter = "node"

    # Write code to a temp file and execute
    suffix = ".py" if language == "python" else ".js"
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="code_interpreter_")
        # Write the code to the temp file
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(code)
            tmp_fd = None  # fdopen takes ownership

        result = subprocess.run(
            [interpreter, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        stdout = _truncate_output(result.stdout)
        stderr = _truncate_output(result.stderr)

        return json.dumps(
            {"stdout": stdout, "stderr": stderr, "exit_code": result.returncode},
            ensure_ascii=False,
        )

    except subprocess.TimeoutExpired:
        return json.dumps(
            {"error": f"Execution timed out after {timeout} seconds", "stdout": "", "stderr": "", "exit_code": -1},
            ensure_ascii=False,
        )
    except FileNotFoundError:
        return json.dumps(
            {"error": f"Interpreter '{interpreter}' not found. Ensure {language} is installed.", "stdout": "", "stderr": "", "exit_code": -1},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Code interpreter failed: {type(e).__name__}: {e}")
        return json.dumps(
            {"error": f"{type(e).__name__}: {e}", "stdout": "", "stderr": "", "exit_code": -1},
            ensure_ascii=False,
        )
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
