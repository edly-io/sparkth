"""Running one action through either transport: events published, a preview's failures recorded."""

from dataclasses import replace

import pytest
from httpx import AsyncClient
from pxc.lib.permission import Permission
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.plugins.pxc.actions import perform_action
from sparkth.plugins.pxc.constants import PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID
from sparkth.plugins.pxc.enums import PxcFailureKind
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcSandboxFailure
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.runtime import build_runtime
from sparkth.plugins.pxc.store import list_action_failures
from sparkth.plugins.pxc.tests.conftest import THROWN_TEXT
from sparkth.plugins.pxc.tokens import LaunchClaims, mint_launch_token


def _preview(activity: PxcActivity) -> LaunchClaims:
    """The claims of the author's own preview of ``activity``."""
    return LaunchClaims(
        str(activity.id), PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID, "sparkth-1", Permission.play
    )


async def test_a_preview_action_whose_sandbox_fails_is_recorded(
    session: AsyncSession, authored_activity: PxcActivity, throwing_sandbox: None
) -> None:
    claims = _preview(authored_activity)

    with pytest.raises(PxcSandboxFailure):
        await perform_action(build_runtime(claims), claims, "answer.submit", [0])

    [failure] = await list_action_failures(session, authored_activity.id, None, 20)
    assert (failure.kind, failure.action, failure.permission) == (PxcFailureKind.FAILED, "answer.submit", "play")
    assert (failure.value, failure.error) == ("[0]", THROWN_TEXT)


async def test_a_preview_action_the_manifest_refuses_is_recorded(
    session: AsyncSession, authored_activity: PxcActivity
) -> None:
    claims = _preview(authored_activity)

    with pytest.raises(PxcActionRejected):
        await perform_action(build_runtime(claims), claims, "no.such.action", {})

    [failure] = await list_action_failures(session, authored_activity.id, None, 20)
    assert failure.kind == PxcFailureKind.REJECTED
    assert "no.such.action" in failure.error


async def test_a_learners_failure_in_a_course_is_not_recorded(
    session: AsyncSession, authored_activity: PxcActivity, throwing_sandbox: None
) -> None:
    claims = replace(_preview(authored_activity), course_id="course-v1:edX+DemoX+2026")

    with pytest.raises(PxcSandboxFailure):
        await perform_action(build_runtime(claims), claims, "answer.submit", [0])

    assert await list_action_failures(session, authored_activity.id, None, 20) == []


async def test_a_failure_that_cannot_be_recorded_still_reaches_the_caller(
    authored_activity: PxcActivity, throwing_sandbox: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.actions.insert_action_failure", _database_down)
    claims = _preview(authored_activity)

    with pytest.raises(PxcSandboxFailure):
        await perform_action(build_runtime(claims), claims, "answer.submit", [0])


async def _database_down(*args: object) -> None:
    """Stand in for ``insert_action_failure`` with a database that refuses the write."""
    raise OperationalError("INSERT", {}, Exception("database is locked"))


async def test_an_oversized_preview_value_is_recorded_trimmed(
    session: AsyncSession, authored_activity: PxcActivity, throwing_sandbox: None
) -> None:
    claims = _preview(authored_activity)

    with pytest.raises(PxcSandboxFailure):
        await perform_action(build_runtime(claims), claims, "config.save", "x" * 10_000)

    [failure] = await list_action_failures(session, authored_activity.id, None, 20)
    assert len(failure.value) == 4000


async def test_a_preview_post_that_fails_is_recorded_and_still_unprocessable(
    client: AsyncClient,
    session: AsyncSession,
    authored_activity: PxcActivity,
    configured_secret: str,
    throwing_sandbox: None,
) -> None:
    token = mint_launch_token(
        str(authored_activity.id),
        PXC_PREVIEW_ACTIVITY_INSTANCE,
        PXC_PREVIEW_COURSE_ID,
        "sparkth-1",
        "play",
        configured_secret,
    )

    response = await client.post("/api/v1/pxc/actions/answer.submit", params={"token": token}, json=[0])

    assert response.status_code == 422
    assert len(await list_action_failures(session, authored_activity.id, None, 20)) == 1
