"""Small local-only administration CLI for the runtime policy and approvals."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path

from .consent import ConsentStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ideer-local-runtime")
    parser.add_argument(
        "--db", type=Path, default=Path.home() / ".ideer" / "local-runtime.db"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    config = sub.add_parser("config-root", help="set the logical workspace root")
    config.add_argument("path", type=Path)
    policy = sub.add_parser("set-policy", help="set a capability policy")
    policy.add_argument("capability")
    policy.add_argument("decision", choices=("allow", "deny", "consent"))
    sub.add_parser("approvals", help="list local approval audit entries")
    sub.add_parser("list-pending", help="list approvals awaiting a local decision")
    runtime = sub.add_parser("start-runtime", help="start the outbound-only runtime")
    runtime.add_argument("--server-url", required=True)
    runtime.add_argument("--device-id", required=True)
    runtime.add_argument("--session-token", required=True)
    runtime.add_argument(
        "--private-key", required=True, help="base64 encoded Ed25519 private key"
    )
    for name in ("approve", "deny"):
        command = sub.add_parser(name)
        command.add_argument("capability")
        command.add_argument("request_hash")
        command.add_argument("--actor", default="local-user")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    store = ConsentStore(db_path=args.db)
    if args.command == "config-root":
        config_path = args.db.with_suffix(".json")
        config_path.write_text(
            json.dumps({"logical_root": str(args.path.resolve())}, indent=2) + "\n"
        )
        print(config_path)
        return 0
    if args.command == "set-policy":
        config_path = args.db.with_suffix(".json")
        current = json.loads(config_path.read_text()) if config_path.exists() else {}
        current.setdefault("policy", {})[args.capability] = args.decision
        config_path.write_text(json.dumps(current, indent=2) + "\n")
        return 0
    if args.command == "start-runtime":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        from .transport import LocalRuntimeClient

        key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(args.private_key))
        client = LocalRuntimeClient(
            server_url=args.server_url,
            device_id=args.device_id,
            session_token=args.session_token,
            private_key=key,
        )
        asyncio.run(client.run())
        return 0
    if args.command in {"approve", "deny"}:
        getattr(store, args.command)(
            args.capability, args.request_hash, actor_id=args.actor
        )
        return 0
    import sqlite3

    with sqlite3.connect(args.db) as db:
        if args.command == "list-pending":
            for row in db.execute(
                "SELECT capability, request_hash, payload FROM pending_consents ORDER BY rowid"
            ):
                print(
                    json.dumps(
                        {
                            "capability": row[0],
                            "request_hash": row[1],
                            "payload": json.loads(row[2]),
                        },
                        ensure_ascii=False,
                    )
                )
            return 0
        for row in db.execute(
            "SELECT capability, request_hash, decision, actor_id, decided_at FROM consent_audit ORDER BY rowid"
        ):
            print(
                json.dumps(
                    dict(
                        zip(
                            (
                                "capability",
                                "request_hash",
                                "decision",
                                "actor_id",
                                "decided_at",
                            ),
                            row,
                        )
                    ),
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
