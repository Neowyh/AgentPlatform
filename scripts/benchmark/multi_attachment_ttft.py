#!/usr/bin/env python3
"""Measure upload and first-token latency for the multi-attachment flow.

The script intentionally talks to a running AgentPlatform gateway and a real
configured model. It does not synthesize model timings or inspect server logs;
the latter remain useful for the stage-level ``first_token_timing`` records.

Example::

    python scripts/benchmark/multi_attachment_ttft.py \
      --thread-id benchmark-thread \
      --assistant-id fault-zeroing \
      --file fixtures/report.pdf \
      --file fixtures/data.xlsx \
      --header 'Cookie=...' \
      --output /tmp/ttft.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx

DEFAULT_COUNTS = (0, 1, 5, 10, 20)
SUPPORTED_FILE_SUFFIXES = {".pdf", ".docx", ".xlsx", ".txt", ".md"}

# Chunk-stream event names whose per-chunk metadata carries LangGraph routing
# keys but no run_id (see _stream_signal).
_CHUNK_EVENT_NAMES = {"messages", "messages-tuple"}


def _parse_header(value: str) -> tuple[str, str]:
    name, separator, content = value.partition("=")
    if not separator or not name.strip():
        raise argparse.ArgumentTypeError("headers must use NAME=VALUE syntax")
    return name.strip(), content


def _text_content(value: Any) -> str:
    """Extract displayable text from a LangChain message content value."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if value.get("type") in {"tool_call", "tool_use", "thinking", "reasoning"}:
            return ""
        return "".join(
            _text_content(value[key])
            for key in ("text", "content", "delta")
            if key in value
        )
    if isinstance(value, (list, tuple)):
        return "".join(_text_content(item) for item in value)
    return ""


def _message_and_metadata(payload: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return the message and stream metadata from a messages-tuple payload."""
    if not isinstance(payload, (list, tuple)) or len(payload) < 2:
        return None, {}
    message = payload[0] if isinstance(payload[0], dict) else None
    metadata = payload[1] if isinstance(payload[1], dict) else {}
    return message, metadata


def _message_role(message: dict[str, Any]) -> str:
    role = message.get("role") or message.get("type") or ""
    return str(role).lower()


def _stream_signal(
    event_name: str, payload: Any, expected_run_id: str | None
) -> tuple[str | None, str | None]:
    """Classify one SSE event without treating user/history/metadata as TTFT.

    Returns ``(signal, run_id)`` where signal is ``assistant``, ``tool``,
    ``sse`` or ``error``. The run id is learned from metadata and used to
    reject events from another run when the gateway includes it.
    """
    if event_name in {"error", "on_error"}:
        return "error", expected_run_id
    if event_name in {"metadata", "run_metadata"} and isinstance(payload, dict):
        run_id = payload.get("run_id") or payload.get("id")
        return "sse", str(run_id) if run_id else expected_run_id
    message, metadata = _message_and_metadata(payload)
    if message is None:
        return ("sse" if payload is not None else None), expected_run_id
    event_run_id = metadata.get("run_id") or message.get("run_id")
    if expected_run_id and not event_run_id and event_name not in _CHUNK_EVENT_NAMES:
        return None, expected_run_id
    # Per-chunk `messages` metadata carries LangGraph routing keys but no
    # run_id; on this dedicated sequential thread such chunks belong to the
    # in-flight run pinned by the leading metadata event. Full-state `values`
    # replays keep the strict match above, so stale runs stay rejected.
    if expected_run_id and event_run_id and str(event_run_id) != expected_run_id:
        return None, expected_run_id
    role = _message_role(message)
    content = _text_content(message.get("content"))
    if not content.strip():
        return None, str(event_run_id) if event_run_id else expected_run_id
    if role in {"human", "user", "system"}:
        return None, str(event_run_id) if event_run_id else expected_run_id
    if role in {"tool", "toolmessage"} or message.get("tool_call_id"):
        return "tool", str(event_run_id) if event_run_id else expected_run_id
    if role in {
        "ai",
        "assistant",
        "aimessage",
        "aimessagechunk",
        "assistantmessagechunk",
    }:
        return "assistant", str(event_run_id) if event_run_id else expected_run_id
    return None, str(event_run_id) if event_run_id else expected_run_id


def _observe_stream(
    events: Iterable[tuple[str, Any]], started_at: float, *, clock=time.perf_counter
) -> dict[str, Any]:
    """Observe a stream with one monotonic clock and return calibrated marks."""
    first_token_ms: float | None = None
    first_tool_ms: float | None = None
    first_sse_ms: float | None = None
    stream_error = False
    expected_run_id: str | None = None
    for event_name, payload in events:
        event_at = clock()
        signal, expected_run_id = _stream_signal(event_name, payload, expected_run_id)
        if first_sse_ms is None:
            first_sse_ms = (event_at - started_at) * 1000
        if signal == "error":
            stream_error = True
        elif signal == "tool" and first_tool_ms is None:
            first_tool_ms = (event_at - started_at) * 1000
        elif signal == "assistant" and first_token_ms is None:
            first_token_ms = (event_at - started_at) * 1000
    return {
        "run_to_first_token_ms": first_token_ms,
        "run_to_first_tool_ms": first_tool_ms,
        "run_to_first_sse_event_ms": first_sse_ms,
        "stream_error": stream_error,
        "run_id": expected_run_id,
    }


def _iter_sse_events(response: httpx.Response) -> Iterable[tuple[str, Any]]:
    event_name = "message"
    data_lines: list[str] = []
    for line in response.iter_lines():
        if line.startswith("event:"):
            event_name = line.partition(":")[2].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line.partition(":")[2].lstrip())
        elif not line and data_lines:
            payload_text = "\n".join(data_lines)
            data_lines = []
            if payload_text == "null":
                payload: Any = None
            else:
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    payload = payload_text
            yield event_name, payload
            event_name = "message"


def _select_files(files: list[Path], count: int) -> list[Path]:
    if count == 0:
        return []
    if not files:
        raise ValueError(
            "at least one --file or --fixture-dir file is required for non-zero scenarios"
        )
    return [files[index % len(files)] for index in range(count)]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.environ.get("TTFT_BASE_URL", "http://127.0.0.1:8001")
    )
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--assistant-id", default=None)
    parser.add_argument("--file", dest="files", action="append", type=Path, default=[])
    parser.add_argument("--fixture-dir", type=Path, default=None)
    parser.add_argument(
        "--count", dest="counts", action="append", type=int, choices=DEFAULT_COUNTS
    )
    parser.add_argument("--label", default="current")
    parser.add_argument("--output", type=Path, default=Path("ttft-results.json"))
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--header", action="append", type=_parse_header, default=[])
    parser.add_argument("--cookie", default=os.environ.get("TTFT_COOKIE"))
    return parser


def _fixture_files(directory: Path | None) -> list[Path]:
    if directory is None:
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_FILE_SUFFIXES
    )


def _headers(args: argparse.Namespace, trace_id: str) -> dict[str, str]:
    headers = dict(args.header)
    if args.cookie:
        headers["Cookie"] = args.cookie
    headers["X-Trace-Id"] = trace_id
    return headers


def _run_scenario(
    client: httpx.Client, args: argparse.Namespace, files: list[Path], count: int
) -> dict[str, Any]:
    trace_id = uuid.uuid4().hex
    selected = _select_files(files, count)
    headers = _headers(args, trace_id)
    scenario_started = time.perf_counter()

    upload_started = time.perf_counter()
    if selected:
        # Prefix repeated fixture selections so every multipart part has a
        # unique client filename; this exercises the product's real duplicate
        # name handling without silently overwriting an earlier upload.
        multipart = [
            (
                "files",
                (
                    f"{index:02d}-{path.name}",
                    path.read_bytes(),
                    "application/octet-stream",
                ),
            )
            for index, path in enumerate(selected)
        ]
        upload_response = client.post(
            f"/api/threads/{args.thread_id}/uploads",
            files=multipart,
            headers=headers,
        )
        upload_response.raise_for_status()
        upload_payload = upload_response.json()
    else:
        upload_payload = {"files": []}
    upload_ms = (time.perf_counter() - upload_started) * 1000

    run_payload = {
        "assistant_id": args.assistant_id,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": "Analyze the uploaded files and summarize the findings.",
                }
            ]
        },
        "context": {"trace_id": trace_id},
        "stream_mode": ["messages-tuple", "values"],
        "on_disconnect": "continue",
    }
    run_started = time.perf_counter()
    first_token_at: float | None = None
    with client.stream(
        "POST",
        f"/api/threads/{args.thread_id}/runs/stream",
        json=run_payload,
        headers=headers,
    ) as response:
        response.raise_for_status()
        observed = _observe_stream(_iter_sse_events(response), run_started)
        first_token_ms = observed["run_to_first_token_ms"]
        first_token_at = (
            run_started + first_token_ms / 1000 if first_token_ms is not None else None
        )

    run_complete_ms = (time.perf_counter() - run_started) * 1000
    end_to_end_ms = (
        None if first_token_at is None else (first_token_at - scenario_started) * 1000
    )
    uploaded_entries = (
        upload_payload.get("files", []) if isinstance(upload_payload, dict) else []
    )
    upload_validation = {
        "success": upload_payload.get("success")
        if isinstance(upload_payload, dict)
        else None,
        "skipped_files": upload_payload.get("skipped_files", [])
        if isinstance(upload_payload, dict)
        else [],
        "response_file_count": len(uploaded_entries),
        "expected_file_count": len(selected),
        "count_matches": len(uploaded_entries) == len(selected),
        "stored_names_unique": len(
            {
                entry.get("filename")
                for entry in uploaded_entries
                if isinstance(entry, dict)
            }
        )
        == len(uploaded_entries),
        "conversion_statuses": [
            {
                key: entry.get(key)
                for key in (
                    "filename",
                    "markdown_file",
                    "markdown_path",
                    "markdown_artifact_url",
                )
                if key in entry
            }
            for entry in uploaded_entries
            if isinstance(entry, dict)
        ],
    }
    return {
        "label": args.label,
        "count": count,
        "trace_id": trace_id,
        "files": [str(path) for path in selected],
        "total_bytes": sum(path.stat().st_size for path in selected),
        "upload_ms": round(upload_ms, 1),
        "run_to_first_token_ms": None
        if first_token_ms is None
        else round(first_token_ms, 1),
        "run_to_first_tool_ms": None
        if observed["run_to_first_tool_ms"] is None
        else round(observed["run_to_first_tool_ms"], 1),
        "run_to_first_sse_event_ms": None
        if observed["run_to_first_sse_event_ms"] is None
        else round(observed["run_to_first_sse_event_ms"], 1),
        "stream_error": observed["stream_error"],
        "run_id": observed["run_id"],
        "end_to_end_ttft_ms": None
        if end_to_end_ms is None
        else round(end_to_end_ms, 1),
        "run_complete_ms": round(run_complete_ms, 1),
        "uploaded_file_count": len(uploaded_entries),
        "upload_validation": upload_validation,
    }


def main() -> int:
    args = _build_parser().parse_args()
    files = [path.resolve() for path in args.files] + _fixture_files(args.fixture_dir)
    missing = [path for path in files if not path.is_file()]
    if missing:
        print(f"missing benchmark file: {missing[0]}", file=sys.stderr)
        return 2
    counts = tuple(args.counts or DEFAULT_COUNTS)
    results: list[dict[str, Any]] = []
    with httpx.Client(
        base_url=args.base_url.rstrip("/"), timeout=args.timeout
    ) as client:
        for count in counts:
            print(f"running count={count}", file=sys.stderr, flush=True)
            results.append(_run_scenario(client, args, files, count))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"base_url": args.base_url, "results": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    missing_token_counts = [
        result["count"] for result in results if result["run_to_first_token_ms"] is None
    ]
    if missing_token_counts:
        print(
            f"no non-empty streamed token observed for count(s): {missing_token_counts}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
