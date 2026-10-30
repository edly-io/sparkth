"""Fire-and-forget tasks the chat plugin runs past the request that spawned them."""

import asyncio
from collections.abc import Coroutine
from typing import Any

# Every detached task is kept here until it finishes, then
# removes itself, so the set never grows.
# Tests drain it to join the work a request left running.
live_tasks: set[asyncio.Task[None]] = set()


def detach(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
    """Run ``coro`` on its own task, kept alive in ``live_tasks`` until it finishes."""
    task = asyncio.create_task(coro)
    live_tasks.add(task)
    task.add_done_callback(live_tasks.discard)
    return task


async def join_live_tasks() -> None:
    """Await every detached task, including any a finishing task detaches in turn.

    Filters on ``done()`` rather than set membership: gathering only finished tasks never
    yields, so their discard callbacks would never run and the loop would spin.
    """
    while pending := [task for task in live_tasks if not task.done()]:
        await asyncio.gather(*pending, return_exceptions=True)
