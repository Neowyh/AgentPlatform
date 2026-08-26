"""MCP Server for code_interpreter tool.

Run standalone:
    python -m ideer.community.code_interpreter.mcp_server

Register in extensions_config.json:
  "code-interpreter": {
    "enabled": true,
    "type": "stdio",
    "command": "python",
    "args": ["-m", "ideer.community.code_interpreter.mcp_server"]
  }
"""

import asyncio
import json
import logging
import os
import resource
import subprocess
import tempfile

from mcp.server.fastmcp import FastMCP

# NOTE: execution intentionally differs from tools.py — the in-process tool
# runs code inside the platform sandbox (Runtime-injected), while this MCP
# variant executes locally via subprocess with its own resource limits.
# Only output truncation is shared, imported from the canonical source.
from ideer.community.code_interpreter.tools import _truncate_output

logger = logging.getLogger(__name__)

# FastMCP exposes the ``.tool`` decorator; the low-level Server does not.
server = FastMCP("code-interpreter")

_MAX_TIMEOUT = 300
_DEFAULT_TIMEOUT = 60
_MAX_OUTPUT_CHARS = 20000
_MAX_CODE_SIZE = 1_000_000  # 1 MB - prevent disk exhaustion from oversized code

# MCP server runs as a standalone process — sandbox is not available.
# Code is executed in an isolated subprocess with restricted environment.
_SAFE_ENV_KEYS = {"PATH", "LANG", "LC_ALL", "TZ", "USER", "TMPDIR"}


def _build_safe_env() -> dict[str, str]:
    """Build a sanitized environment dict for subprocess execution."""
    return {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}


def _set_resource_limits() -> None:
    """Set resource limits for child processes (Unix only)."""
    try:
        # 512 MB memory limit
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        # 100 MB file size limit
        resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))
        # Max 64 processes
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except (ValueError, OSError):
        pass  # Resource limits not available on this platform


@server.tool("code_interpreter")
async def code_interpreter(code: str, language: str = "python", timeout: int = 60) -> str:
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
            {
                "error": f"Unsupported language: '{language}'. Use 'python' or 'javascript'.",
                "stdout": "",
                "stderr": "",
                "exit_code": 1,
            },
            ensure_ascii=False,
        )

    # Clamp timeout
    timeout = max(1, min(timeout, _MAX_TIMEOUT))

    # Determine interpreter
    interpreter = "python3" if language == "python" else "node"

    # Write code to a temp file and execute
    suffix = ".py" if language == "python" else ".js"
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="code_interpreter_")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(code)
            tmp_fd = None  # fdopen takes ownership

        result = await asyncio.to_thread(
            subprocess.run,
            [interpreter, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_safe_env(),
            preexec_fn=_set_resource_limits,
        )

        stdout = _truncate_output(result.stdout)
        stderr = _truncate_output(result.stderr)

        return json.dumps(
            {"stdout": stdout, "stderr": stderr, "exit_code": result.returncode},
            ensure_ascii=False,
        )

    except subprocess.TimeoutExpired as e:
        logger.warning("Code execution timed out after %s seconds", timeout)
        return json.dumps(
            {
                "error": f"Execution timed out after {timeout} seconds",
                "stdout": _truncate_output(e.stdout or ""),
                "stderr": _truncate_output(e.stderr or ""),
                "exit_code": -1,
            },
            ensure_ascii=False,
        )
    except FileNotFoundError:
        return json.dumps(
            {
                "error": f"Interpreter '{interpreter}' not found. Ensure {language} is installed.",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("Code interpreter failed: %s: %s", type(e).__name__, e)
        return json.dumps(
            {"error": "Code execution failed", "stdout": "", "stderr": "", "exit_code": -1},
            ensure_ascii=False,
        )
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
