"""Seed the prerequisites the Playwright E2E suite assumes already exist.

Three things are created, all idempotently (existing rows are left untouched):

1. The built-in `sparkth_user` and `plugin_user` roles, when missing: a database built
   from models carries no roles, and every account must hold both.
2. The account `frontend/e2e-tests/auth.setup.ts` logs in as. Created
   email-verified so login succeeds without the mail round-trip, and given both roles.
3. The `@example.com` whitelist entry. `randomUser()` in
   `frontend/e2e-tests/utils/user.ts` generates `@example.com` addresses, and
   registration enforces a domain whitelist (`sparkth/services/whitelist.py`), so an
   empty table 403s every sign-up.

Mirrors the seed steps in `.github/workflows/playwright.yml`. Credentials default
to the values in `frontend/e2e-tests/config.ts` and can be overridden via the
`FIRST_SUPERUSER`, `FIRST_SUPERUSER_EMAIL`, and `FIRST_SUPERUSER_PASSWORD`
environment variables.
"""

import asyncio
import os
from typing import cast

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.db import dispose_engine
from sparkth.core.models.base import utc_now
from sparkth.core.models.user import User
from sparkth.core.models.whitelist import WhitelistedEmail
from sparkth.core.permissions.models import Role, RolePermission
from sparkth.core.permissions.roles import available_permissions
from sparkth.core.security import get_password_hash
from sparkth.lib.db import session_scope
from sparkth.lib.permissions import PLUGIN_USE, PLUGIN_USER_ROLE, SPARKTH_USER_ROLE, assign_default_roles
from sparkth.lib.plugins import get_plugin_loader


async def ensure_role(name: str, permissions: list[str], session: AsyncSession) -> None:
    """Create the built-in role `name` holding `permissions` unless it already exists."""
    if (await session.exec(select(Role).where(Role.name == name))).first():
        return
    role = Role(name=name, is_builtin=True)
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    await session.commit()
    print(f"role '{name}' created")


async def seed() -> None:
    username = os.environ.get("FIRST_SUPERUSER", "admin")
    email = os.environ.get("FIRST_SUPERUSER_EMAIL", "admin@sparkth.local")
    password = os.environ.get("FIRST_SUPERUSER_PASSWORD", "Sparkth-admin-1!")

    # Load the plugins so the permission registry carries their declared permissions.
    get_plugin_loader()
    async with session_scope() as session:
        await ensure_role(SPARKTH_USER_ROLE, available_permissions(), session)
        await ensure_role(PLUGIN_USER_ROLE, [PLUGIN_USE.name], session)
        user = (await session.exec(select(User).where((User.username == username) | (User.email == email)))).first()
        if user:
            print(f"superuser '{username}' already present")
        else:
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                name=username,
                email_verified=True,
                email_verified_at=utc_now(),
            )
            session.add(user)
            await session.flush()
            print(f"superuser '{username}' created")
        await assign_default_roles(cast(int, user.id), session)
        await session.commit()

        existing_whitelist = (
            await session.exec(select(WhitelistedEmail).where(WhitelistedEmail.value == "@example.com"))
        ).first()
        if existing_whitelist:
            print("whitelist '@example.com' already present")
        else:
            session.add(WhitelistedEmail(value="@example.com", entry_type="domain"))
            await session.commit()
            print("whitelist '@example.com' created")


def main() -> None:
    async def _run() -> None:
        try:
            await seed()
        finally:
            # Dispose so aiosqlite's connection worker thread exits; otherwise the
            # process hangs at interpreter shutdown waiting to join it.
            await dispose_engine()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
