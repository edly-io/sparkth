"""Seed the prerequisites the Playwright E2E suite assumes already exist.

Two things are created, both idempotently (existing rows are left untouched):

1. The superuser `frontend/tests/auth.setup.ts` logs in as. Created
   email-verified so login succeeds without the mail round-trip.
2. The `@example.com` whitelist entry. `randomUser()` in
   `frontend/tests/utils/user.ts` generates `@example.com` addresses, and
   registration enforces a domain whitelist (`app/services/whitelist.py`), so an
   empty table 403s every sign-up.

Mirrors the seed steps in `.github/workflows/playwright.yml`. Credentials default
to the values in `frontend/tests/config.ts` and can be overridden via the
`FIRST_SUPERUSER`, `FIRST_SUPERUSER_EMAIL`, and `FIRST_SUPERUSER_PASSWORD`
environment variables.
"""

import asyncio
import os

from sqlmodel import select

from app.core.db import async_engine
from app.core.security import get_password_hash
from app.lib.db import session_scope
from app.models.base import utc_now
from app.models.user import User
from app.models.whitelist import WhitelistedEmail


async def seed() -> None:
    username = os.environ.get("FIRST_SUPERUSER", "admin")
    email = os.environ.get("FIRST_SUPERUSER_EMAIL", "admin@sparkth.local")
    password = os.environ.get("FIRST_SUPERUSER_PASSWORD", "Sparkth-admin-1!")

    async with session_scope() as session:
        existing_user = (
            await session.exec(select(User).where((User.username == username) | (User.email == email)))
        ).first()
        if existing_user:
            print(f"superuser '{username}' already present")
        else:
            session.add(
                User(
                    username=username,
                    email=email,
                    hashed_password=get_password_hash(password),
                    name=username,
                    is_superuser=True,
                    email_verified=True,
                    email_verified_at=utc_now(),
                )
            )
            await session.commit()
            print(f"superuser '{username}' created")

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
            await async_engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
