"""Structured concurrency helpers built on anyio."""

from collections.abc import Awaitable
from typing import TypeVar, cast

import anyio

T = TypeVar("T")


async def gather(*awaitables: Awaitable[T]) -> list[T]:
    """Run awaitables concurrently; results match input order."""
    if not awaitables:
        return []
    results: list[T | None] = [None] * len(awaitables)

    async with anyio.create_task_group() as tg:

        async def run(index: int, aw: Awaitable[T]) -> None:
            results[index] = await aw

        for i, aw in enumerate(awaitables):
            tg.start_soon(run, i, aw)

    return cast(list[T], results)
