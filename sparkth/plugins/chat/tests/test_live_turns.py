"""The registry that lets a stop request reach the turn it names."""

import pytest

from sparkth.plugins.chat.routes.utils.live_turns import (
    register_turn,
    release_turn,
    request_stop,
)


@pytest.mark.asyncio
async def test_stop_sets_the_event_of_a_registered_turn() -> None:
    stop_requested = register_turn("turn-1", user_id=7)
    try:
        assert request_stop("turn-1", user_id=7) is True
        assert stop_requested.is_set()
    finally:
        release_turn("turn-1", user_id=7)


@pytest.mark.asyncio
async def test_stop_is_refused_for_an_unknown_turn() -> None:
    assert request_stop("never-registered", user_id=7) is False


@pytest.mark.asyncio
async def test_stop_is_refused_for_another_users_turn() -> None:
    stop_requested = register_turn("turn-2", user_id=7)
    try:
        assert request_stop("turn-2", user_id=8) is False
        assert not stop_requested.is_set()
    finally:
        release_turn("turn-2", user_id=7)


@pytest.mark.asyncio
async def test_a_released_turn_can_no_longer_be_stopped() -> None:
    register_turn("turn-3", user_id=7)
    release_turn("turn-3", user_id=7)
    assert request_stop("turn-3", user_id=7) is False


@pytest.mark.asyncio
async def test_releasing_an_unknown_turn_is_harmless() -> None:
    release_turn("never-registered", user_id=7)


@pytest.mark.asyncio
async def test_the_same_id_registered_by_two_users_stays_two_turns() -> None:
    """Turn ids come from the client, so one caller must not be able to reach another's turn
    by naming its id — each stop reaches only the turn its own caller registered."""
    mine = register_turn("shared-id", user_id=7)
    theirs = register_turn("shared-id", user_id=8)
    try:
        assert request_stop("shared-id", user_id=7) is True
        assert mine.is_set()
        assert not theirs.is_set()
    finally:
        release_turn("shared-id", user_id=7)
        release_turn("shared-id", user_id=8)


@pytest.mark.asyncio
async def test_releasing_one_users_turn_leaves_the_others_live() -> None:
    register_turn("shared-id-2", user_id=7)
    register_turn("shared-id-2", user_id=8)
    release_turn("shared-id-2", user_id=7)
    try:
        assert request_stop("shared-id-2", user_id=8) is True
    finally:
        release_turn("shared-id-2", user_id=8)
