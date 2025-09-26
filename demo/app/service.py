"""Service."""

import asyncio
import time


async def run_query(input_text: str) -> str:
    """Run a query."""
    return f"some output based on {input_text!r}"


async def run_async_job(input_text: str) -> str:
    """Run a long running job."""
    await asyncio.sleep(60)
    return f"some output based on {input_text!r}$"


def run_sync_job(input_text: str) -> str:
    """Run a long running job."""
    time.sleep(60)
    return f"some output based on {input_text!r}$"
