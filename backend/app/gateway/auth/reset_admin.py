"""CLI tool to reset an admin password.

Usage:
    python -m app.gateway.auth.reset_admin
    python -m app.gateway.auth.reset_admin --email admin@example.com

Writes the new password to ``.ideer/admin_initial_credentials.txt``
(mode 0600) instead of printing it, so CI / log aggregators never see
the cleartext secret.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import select

from app.gateway.auth.credential_file import write_initial_credentials
from app.gateway.auth.password import hash_password
from app.gateway.auth.repositories.sqlite import SQLiteUserRepository
from ideer.persistence.models.user import UserModel, UserRole


async def _run(email: str | None) -> int:
    from ideer.config import get_app_config
    from ideer.persistence.engine import (
        close_engine,
        get_session_factory,
        init_engine_from_config,
    )

    config = get_app_config()
    await init_engine_from_config(config.database)
    try:
        sf = get_session_factory()
        if sf is None:
            print("Error: persistence engine not available (check config.database).", file=sys.stderr)
            return 1

        repo = SQLiteUserRepository(sf)

        if email:
            user = await repo.get_user_by_email(email)
            if user is not None:
                async with sf() as session:
                    stmt = select(UserModel).where(
                        UserModel.id == str(user.id),
                        UserModel.role == UserRole.SUPER_ADMIN,
                        UserModel.disabled.is_not(True),
                    )
                    if (await session.execute(stmt)).scalar_one_or_none() is None:
                        user = None
        else:
            # Find first active RBAC super_admin.
            async with sf() as session:
                stmt = (
                    select(UserModel)
                    .where(
                        UserModel.role == UserRole.SUPER_ADMIN,
                        UserModel.disabled.is_not(True),
                    )
                    .limit(1)
                )
                row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                user = None
            else:
                user = await repo.get_user_by_id(row.id)

        if user is None:
            if email:
                print(f"Error: active super_admin user '{email}' not found.", file=sys.stderr)
            else:
                print("Error: no active super_admin user found. Initialize the system first.", file=sys.stderr)
            return 1

        new_password = secrets.token_urlsafe(16)
        user.password_hash = hash_password(new_password)
        user.token_version += 1
        user.needs_setup = True
        await repo.update_user(user)

        cred_path = write_initial_credentials(user.email, new_password, label="reset")
        print(f"Password reset for: {user.email}")
        print(f"Credentials written to: {cred_path} (mode 0600)")
        print("Next login will require setup (new email + password).")
        return 0
    finally:
        await close_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset admin password")
    parser.add_argument("--email", help="Admin email (default: first admin found)")
    args = parser.parse_args()

    exit_code = asyncio.run(_run(args.email))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
