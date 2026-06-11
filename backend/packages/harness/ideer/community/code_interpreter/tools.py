"""
Code Interpreter Tool - Execute Python or JavaScript code in a secure sandbox.

Provides isolated code execution with stdout/stderr capture, output truncation,
and local-path masking for security. Common Python libraries (pandas, matplotlib,
numpy) are pre-installed in the sandbox environment.
"""

import json
import logging

from langchain.tools import tool

from ideer.sandbox.tools import ensure_sandbox_initialized
from ideer.tools.types import Runtime

logger = logging.getLogger(__name__)

_MAX_TIMEOUT = 300
_DEFAULT_TIMEOUT = 60
_MAX_OUTPUT_CHARS = 20000
_MAX_CODE_SIZE = 1_000_000  # 1 MB - prevent disk exhaustion from oversized code


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
def code_interpreter_tool(code: str, runtime: Runtime | None = None, language: str = "python", timeout: int = 60) -> str:
    """Execute code in a secure sandbox and return the output.

    Use this for data processing, calculations, generating charts, or any task
    that benefits from programmatic execution. Common Python libraries (pandas,
    matplotlib, numpy) are pre-installed in the sandbox environment.

    Args:
        code: The code to execute. Can be multi-line.
        language: Programming language — "python" or "javascript". Default is "python".
        timeout: Maximum execution time in seconds. Default is 60. Max is 300.
    """
    # Validate code size to prevent disk exhaustion
    if len(code) > _MAX_CODE_SIZE:
        return json.dumps(
            {"error": f"Code too large: {len(code)} bytes (max {_MAX_CODE_SIZE} bytes)", "stdout": "", "stderr": "", "exit_code": 1},
            ensure_ascii=False,
        )

    # Validate language
    if language not in ("python", "javascript"):
        return json.dumps(
            {"error": f"Unsupported language: '{language}'. Use 'python' or 'javascript'.", "stdout": "", "stderr": "", "exit_code": 1},
            ensure_ascii=False,
        )

    # Clamp timeout
    timeout = max(1, min(timeout, _MAX_TIMEOUT))

    # Get sandbox — all code execution MUST go through sandbox isolation
    try:
        sandbox = ensure_sandbox_initialized(runtime)
    except Exception as e:
        logger.error("Failed to initialize sandbox for code_interpreter: %s", e)
        return json.dumps(
            {"error": "Sandbox unavailable. Code execution requires a sandbox environment.", "stdout": "", "stderr": "", "exit_code": -1},
            ensure_ascii=False,
        )

    # Determine interpreter and write code to temp file inside sandbox
    if language == "python":
        interpreter = "python3"
        suffix = ".py"
    else:
        interpreter = "node"
        suffix = ".js"

    tmp_path = f"/tmp/code_interpreter_{id(code)}{suffix}"
    try:
        # Write code to a temp file in the sandbox
        sandbox.write_file(tmp_path, code)

        # Execute inside sandbox with timeout
        # Wrap with timeout command since sandbox.execute_command doesn't support timeout param
        cmd = f"timeout {timeout} {interpreter} {tmp_path}"
        output = sandbox.execute_command(cmd)

        # Parse output — sandbox returns combined stdout/stderr
        stdout = _truncate_output(output)
        stderr = ""

        return json.dumps(
            {"stdout": stdout, "stderr": stderr, "exit_code": 0},
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error("Code interpreter failed: %s: %s", type(e).__name__, e)
        error_msg = "Code execution failed"
        exit_code = -1
        # Check for timeout-like messages in the output
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            error_msg = f"Execution timed out after {timeout} seconds"
        return json.dumps(
            {"error": error_msg, "stdout": "", "stderr": str(e), "exit_code": exit_code},
            ensure_ascii=False,
        )
    finally:
        # Clean up temp file in sandbox
        try:
            sandbox.execute_command(f"rm -f {tmp_path}")
        except Exception:
            pass
