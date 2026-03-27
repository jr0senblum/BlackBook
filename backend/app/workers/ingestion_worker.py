"""Background ingestion worker — in-process asyncio task queue.

Consumes source IDs from an asyncio.Queue, creates a fresh database session
per job, and delegates to IngestionService.process_source().
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class IngestionQueue:
    """Simple in-process asyncio task queue for source processing.

    The queue holds source IDs. A single worker loop dequeues and processes
    them one at a time. The worker never crashes — exceptions are logged
    and the loop continues.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._session_factory: async_sessionmaker | None = None
        self._build_ingestion_service: Callable | None = None

    def configure(
        self,
        *,
        session_factory: async_sessionmaker,
        build_ingestion_service: Callable,
    ) -> None:
        """Provide the session factory and service builder.

        ``build_ingestion_service`` is a callable that accepts an
        ``AsyncSession`` and returns a fully wired ``IngestionService``.
        """
        self._session_factory = session_factory
        self._build_ingestion_service = build_ingestion_service

    async def enqueue(self, source_id: str) -> None:
        """Add a source ID to the processing queue."""
        await self._queue.put(source_id)

    async def start_worker(self) -> None:
        """Start the background worker loop as an asyncio task."""
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Ingestion worker started")

    async def stop_worker(self) -> None:
        """Cancel the worker task."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("Ingestion worker stopped")

    async def _worker_loop(self) -> None:
        """Continuously dequeue and process source IDs."""
        while True:
            source_id = await self._queue.get()
            try:
                await self._process_job(source_id)
            except Exception:
                logger.exception(
                    "Unhandled error processing source %s", source_id
                )
            finally:
                self._queue.task_done()

    async def _process_job(self, source_id: str) -> None:
        """Process a single source within its own database session."""
        if self._session_factory is None or self._build_ingestion_service is None:
            logger.error(
                "Ingestion queue not configured — cannot process source %s",
                source_id,
            )
            return

        async with self._session_factory() as session:
            async with session.begin():
                service = self._build_ingestion_service(session)
                await service.process_source(source_id)


# Module-level singleton.
ingestion_queue = IngestionQueue()
