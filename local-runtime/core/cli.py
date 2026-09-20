"""Small local-only administration CLI for the runtime policy and approvals."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

from .consent import ConsentStore
from .secrets import (
    InMemorySecretStore,
    SecretStore,
    SecretStoreError,
    create_default_secret_store,
    secret_ref,
)

SECRET_COMMANDS = {"secret-set", "secret-rotate", "secret-delete", "secret-list"}


def _secret_backend_option() -> argparse.ArgumentParser:
    backend = argparse.ArgumentParser(add_help=False)
    backend.add_argument(
        "--backend",
        choices=("auto", "memory"),
        default="auto",
        help="secret store backend: the OS secure store or an in-memory store",
    )
    return backend


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
    runtime = sub.add_parser(
        "start-runtime",
        parents=[_secret_backend_option()],
        help="start the outbound-only runtime",
    )
    runtime.add_argument("--server-url", required=True)
    runtime.add_argument("--device-id", required=True)
    runtime.add_argument("--session-token", required=True)
    runtime.add_argument(
        "--private-key", required=True, help="base64 encoded Ed25519 private key"
    )
    runtime.add_argument(
        "--mcp-config",
        type=Path,
        default=None,
        help="path to the local MCP server config (JSON); servers launch at startup",
    )
    for name in ("approve", "deny"):
        command = sub.add_parser(name)
        command.add_argument("capability")
        command.add_argument("request_hash")
        command.add_argument("--actor", default="local-user")
    backend = _secret_backend_option()
    secret_set = sub.add_parser(
        "secret-set", parents=[backend], help="store a credential value"
    )
    secret_set.add_argument("name")
    secret_set.add_argument(
        "--value", help="credential value; read from stdin when omitted"
    )
    secret_rotate = sub.add_parser(
        "secret-rotate", parents=[backend], help="replace an existing credential"
    )
    secret_rotate.add_argument("name")
    secret_rotate.add_argument(
        "--value", help="credential value; read from stdin when omitted"
    )
    secret_delete = sub.add_parser(
        "secret-delete", parents=[backend], help="remove a stored credential"
    )
    secret_delete.add_argument("name")
    sub.add_parser(
        "secret-list", parents=[backend], help="list stored secret names (never values)"
    )
    return parser


def _read_secret_value() -> str:
    # Read to EOF so multi-line credentials such as SSH private keys work;
    # interactive users finish with Ctrl-D.
    value = sys.stdin.read().rstrip("\r\n")
    if not value:
        raise ValueError("a credential value must not be empty")
    return value


def _run_secret_command(args: argparse.Namespace, store: SecretStore | None) -> int:
    try:
        secret_store = store
        if secret_store is None:
            secret_store = (
                InMemorySecretStore() if args.backend == "memory"
                else create_default_secret_store()
            )
        if args.command == "secret-set":
            value = args.value if args.value is not None else _read_secret_value()
            secret_store.set(args.name, value)
            print(secret_ref(args.name))
        elif args.command == "secret-rotate":
            secret_store.get(args.name)
            value = args.value if args.value is not None else _read_secret_value()
            secret_store.set(args.name, value)
            print(secret_ref(args.name))
        elif args.command == "secret-delete":
            secret_store.delete(args.name)
        elif args.command == "secret-list":
            for name in secret_store.names():
                print(name)
        return 0
    except SecretStoreError as exc:
        print(f"error: {exc.code}: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: INVALID_SECRET: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None, *, store: SecretStore | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in SECRET_COMMANDS:
        return _run_secret_command(args, store)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    consent_store = ConsentStore(db_path=args.db)
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

        from .mcp import LocalMCPService, MCPSupervisor, load_mcp_specs
        from .transport import LocalRuntimeClient

        key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(args.private_key))
        mcp_service = None
        supervisor = None
        if args.mcp_config is not None:
            secret_store = (
                InMemorySecretStore() if args.backend == "memory"
                else create_default_secret_store()
            )

            def resolve_secret(name: str) -> str | None:
                try:
                    return secret_store.get(name)
                except SecretStoreError:
                    return None

            supervisor = MCPSupervisor(
                load_mcp_specs(args.mcp_config),
                secret_resolver=resolve_secret,
            )
            mcp_service = LocalMCPService(supervisor)

        client = LocalRuntimeClient(
            server_url=args.server_url,
            device_id=args.device_id,
            session_token=args.session_token,
            private_key=key,
            mcp_service=mcp_service,
        )

        async def run_runtime() -> None:
            if supervisor is not None:
                await supervisor.start_all()
            try:
                await client.run()
            finally:
                if supervisor is not None:
                    await supervisor.stop_all()

        asyncio.run(run_runtime())
        return 0
    if args.command in {"approve", "deny"}:
        getattr(consent_store, args.command)(
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
