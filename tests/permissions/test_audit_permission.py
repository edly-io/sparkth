from typing import cast

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.testing import grant_global_permission


async def test_audit_read_is_a_known_permission(client: AsyncClient, current_user: User) -> None:
    response = await client.get("/api/v1/permissions/can", params={"permission": "audit.read"})

    assert response.status_code == 200
    assert response.json() == {"allowed": False}


async def test_a_global_audit_read_grant_is_honoured(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await grant_global_permission(session, cast(int, current_user.id), "audit.read")
    await session.commit()

    response = await client.get("/api/v1/permissions/can", params={"permission": "audit.read"})

    assert response.json() == {"allowed": True}
