"""Administrators read the audit trail through the REST API: a filtered, paginated
listing, the categories it can be filtered by, and a streamed CSV / JSON Lines export,
all gated by ``audit.read``.
Authored with LLM (Claude) assistance."""

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import cast

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent
from sparkth.core.models.user import User
from sparkth.lib.audit import record_event
from sparkth.lib.audit.context import UserActor
from sparkth.lib.audit.events import AuditOutcome, AuditTarget, LoginAuditEvent, WhitelistEntryAddedAuditEvent
from sparkth.lib.testing import AuditEventsFetcher, grant_global_permission

NOW = datetime.now(timezone.utc)
ALICE = UserActor(id="7", label="alice")
BOB = UserActor(id="8", label="bob")


async def _seed(session: AsyncSession) -> None:
    await record_event(
        session,
        LoginAuditEvent(outcome=AuditOutcome.SUCCESS, actor=ALICE, occurred_at=NOW - timedelta(days=3)),
    )
    await record_event(
        session,
        LoginAuditEvent(outcome=AuditOutcome.FAILURE, actor=BOB, occurred_at=NOW - timedelta(days=2)),
    )
    await record_event(
        session,
        WhitelistEntryAddedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            actor=ALICE,
            occurred_at=NOW - timedelta(days=1),
            target=AuditTarget(type="whitelist_entry", id="3"),
        ),
    )
    await session.commit()


async def _grant(session: AsyncSession, user: User) -> None:
    await grant_global_permission(session, cast(int, user.id), "audit.read")
    await session.commit()


async def test_listing_requires_audit_read(client: AsyncClient, current_user: User) -> None:
    assert (await client.get("/api/v1/audit/events")).status_code == 403
    assert (await client.get("/api/v1/audit/categories")).status_code == 403
    assert (await client.get("/api/v1/audit/events/export")).status_code == 403


async def test_lists_newest_first_without_canonical_bytes(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await _grant(session, current_user)
    await _seed(session)

    response = await client.get("/api/v1/audit/events")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["category"] + "." + i["action"] for i in items] == [
        "whitelist.entry_added",
        "auth.login",
        "auth.login",
    ]
    assert items[0]["actor_label"] == "alice"
    assert items[0]["target_id"] == "3"
    assert "canonical_bytes" not in items[0]
    assert response.json()["next_before_id"] is None


async def test_filters_combine(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await _grant(session, current_user)
    await _seed(session)

    by_category = await client.get("/api/v1/audit/events", params={"category": "auth", "outcome": "failure"})
    assert [i["actor_id"] for i in by_category.json()["items"]] == ["8"]

    by_actor = await client.get("/api/v1/audit/events", params={"actor_id": "7"})
    assert len(by_actor.json()["items"]) == 2

    window = await client.get(
        "/api/v1/audit/events",
        params={"from": (NOW - timedelta(days=2, hours=1)).isoformat(), "to": NOW.isoformat()},
    )
    assert len(window.json()["items"]) == 2


async def test_paginates_with_before_id(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await _grant(session, current_user)
    await _seed(session)

    first = (await client.get("/api/v1/audit/events", params={"limit": 2})).json()
    assert len(first["items"]) == 2
    assert first["next_before_id"] == first["items"][-1]["id"]

    second = (
        await client.get("/api/v1/audit/events", params={"limit": 2, "before_id": first["next_before_id"]})
    ).json()
    assert [i["action"] for i in second["items"]] == ["login"]
    assert second["next_before_id"] is None


async def test_rejects_a_range_that_ends_before_it_starts(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await _grant(session, current_user)

    response = await client.get(
        "/api/v1/audit/events", params={"from": NOW.isoformat(), "to": (NOW - timedelta(days=1)).isoformat()}
    )

    assert response.status_code == 422


async def test_an_event_shows_every_column_but_the_sealed_bytes(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await _grant(session, current_user)
    await _seed(session)

    item = (await client.get("/api/v1/audit/events")).json()["items"][0]

    assert set(item) == set(AuditEvent.model_fields) - {"canonical_bytes", "created_at", "updated_at"}


async def test_lists_the_registered_categories(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await _grant(session, current_user)

    response = await client.get("/api/v1/audit/categories")

    assert response.status_code == 200
    categories = response.json()
    assert {"audit", "auth", "role", "tool", "whitelist"} <= set(categories)
    assert categories == sorted(set(categories))


async def test_exports_csv_and_records_the_export(
    client: AsyncClient, session: AsyncSession, current_user: User, audit_events: AuditEventsFetcher
) -> None:
    await _grant(session, current_user)
    await _seed(session)

    response = await client.get("/api/v1/audit/events/export", params={"category": "auth"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [r["actor_label"] for r in rows] == ["bob", "alice"]

    exported = (await audit_events())[-1]
    assert (exported.category, exported.action) == ("audit", "exported")
    assert exported.actor_id == str(current_user.id)
    assert exported.new_values == {"format": "csv", "filters": {"category": "auth"}}


@pytest.mark.parametrize("label", ['=HYPERLINK("http://x")', "+1", "-1", "@SUM(A1)", "\tx", "\rx"])
async def test_csv_export_neutralizes_formula_cells(
    client: AsyncClient, session: AsyncSession, current_user: User, label: str
) -> None:
    await _grant(session, current_user)
    await record_event(session, LoginAuditEvent(outcome=AuditOutcome.FAILURE, actor=UserActor(id="9", label=label)))
    await session.commit()

    response = await client.get("/api/v1/audit/events/export", params={"action": "login"})

    rows = list(csv.DictReader(io.StringIO(response.text, newline="")))
    assert [r["actor_label"] for r in rows] == ["'" + label]


async def test_exports_json_lines(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await _grant(session, current_user)
    await _seed(session)

    response = await client.get("/api/v1/audit/events/export", params={"format": "jsonl", "actor_id": "7"})

    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.splitlines()]
    assert [line["action"] for line in lines] == ["entry_added", "login"]


async def test_export_streams_past_one_batch(
    client: AsyncClient, session: AsyncSession, current_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sparkth.services.audit.service.EXPORT_BATCH_SIZE", 2)
    await _grant(session, current_user)
    await _seed(session)

    response = await client.get("/api/v1/audit/events/export", params={"format": "jsonl", "category": "auth"})

    assert [json.loads(line)["actor_label"] for line in response.text.splitlines()] == ["bob", "alice"]
    everything = await client.get("/api/v1/audit/events/export", params={"format": "jsonl", "to": NOW.isoformat()})
    assert len(everything.text.splitlines()) == 3
