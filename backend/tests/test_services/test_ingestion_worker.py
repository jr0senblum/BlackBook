"""Tests for IngestionQueue — the background worker task queue."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers.ingestion_worker import IngestionQueue


# ═════════════════════════════════════════════════════════════════
# Unconfigured guard
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_process_job_unconfigured_logs_error(caplog) -> None:
    """_process_job on an unconfigured queue logs an error and returns without crashing."""
    queue = IngestionQueue()
    # Do NOT call queue.configure() — leave it unconfigured.
    with caplog.at_level(logging.ERROR):
        await queue._process_job("some-source-id")
    assert "not configured" in caplog.text


# ═════════════════════════════════════════════════════════════════
# Exception resilience — worker must not crash
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_survives_process_source_exception() -> None:
    """Worker loop continues processing after process_source raises an unexpected exception."""
    queue = IngestionQueue()

    # Build a mock service whose process_source raises on the first call
    # and succeeds on the second.
    call_count = 0
    processed_ids: list[str] = []

    async def mock_process_source(source_id: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Unexpected boom")
        processed_ids.append(source_id)

    mock_service = MagicMock()
    mock_service.process_source = mock_process_source

    # Create a mock session factory that returns a context manager
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()

    # The session factory returns an async context manager that yields mock_session
    class _FakeSessionCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    class _FakeBeginCtx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            pass

    mock_session.begin = _FakeBeginCtx
    mock_session_factory.return_value = _FakeSessionCtx()

    # We need a new _FakeSessionCtx per call, so use side_effect
    mock_session_factory.side_effect = lambda: _FakeSessionCtx()

    queue.configure(
        session_factory=mock_session_factory,
        build_ingestion_service=lambda db: mock_service,
    )

    # Enqueue two jobs
    await queue.enqueue("fail-id")
    await queue.enqueue("success-id")

    # Start worker, let it process both, then stop
    await queue.start_worker()
    # Wait for the queue to drain
    await asyncio.wait_for(queue._queue.join(), timeout=5.0)
    await queue.stop_worker()

    # The first job raised, but the worker survived and processed the second
    assert "success-id" in processed_ids
    assert call_count == 2


# ═════════════════════════════════════════════════════════════════
# Start / stop lifecycle
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_start_and_stop() -> None:
    """start_worker creates a task; stop_worker cancels it cleanly."""
    queue = IngestionQueue()
    assert queue._task is None

    await queue.start_worker()
    assert queue._task is not None
    assert not queue._task.done()

    await queue.stop_worker()
    assert queue._task is None


@pytest.mark.asyncio(loop_scope="session")
async def test_stop_worker_when_not_started() -> None:
    """stop_worker is a no-op when the worker was never started."""
    queue = IngestionQueue()
    # Should not raise
    await queue.stop_worker()
    assert queue._task is None
