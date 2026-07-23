"""
Comprehensive Test Suite for the Phase 06 Event Bus Architecture.

Covers Event Validation, Publisher Backoff, Subscriber Async Bridging,
Dispatcher Routing & DLQ, SQLite Persistence, and Event Scheduler accuracy.
"""

import asyncio
import time
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.dispatcher import EventDispatcher
from src.core.event_bus import EventBus
from src.core.event_persistence import EventStatus, SQLiteEventStore
from src.core.event_scheduler import EventScheduler
from src.core.events import Event
from src.core.metrics import MetricsRegistry
from src.core.publisher import EventPublisher, PublisherError
from src.core.subscriber import EventSubscriber


# ==========================================
# Fixtures
# ==========================================
@pytest.fixture
def metrics() -> MetricsRegistry:
    return MetricsRegistry()


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "test_events.db")


@pytest.fixture
def store(db_path) -> SQLiteEventStore:
    return SQLiteEventStore(db_path)


@pytest.fixture
def queue() -> asyncio.PriorityQueue:
    return asyncio.PriorityQueue()


# ==========================================
# Event Model & Validation Tests
# ==========================================
@pytest.mark.asyncio
async def test_event_envelope_validation():
    """Validates that Pydantic enforces strict schema rules on the envelope."""
    # Valid payload
    e = Event(topic="video.rendered", payload={"path": "/a.mp4"})
    assert e.event_id is not None
    assert e.timestamp is not None
    
    # Invalid (Missing required 'topic')
    with pytest.raises(ValidationError):
        Event(payload={})


# ==========================================
# Publisher Backoff Tests
# ==========================================
@pytest.mark.asyncio
async def test_publisher_backoff_and_timeout(metrics):
    """
    Simulates a severe CPU spike that fills the queue. 
    Verifies that the Publisher correctly backs off and eventually errors 
    rather than freezing the master loop forever.
    """
    bus = EventBus(metrics)
    # Artificially limit the queue to 1 slot to force instant congestion
    bus._queue = asyncio.PriorityQueue(maxsize=1)
    
    # Fill the single slot
    e1 = Event(topic="fill", payload={})
    bus._queue.put_nowait((1, time.time(), e1))
    
    pub = EventPublisher(bus, metrics)
    start = time.time()
    
    with pytest.raises(PublisherError):
        # max_retries=1 means it will fail the timeout (0.1s), wait (0.5s), 
        # try again, fail timeout (0.1s), then raise an error.
        await pub.publish("drop.test", {}, timeout_sec=0.1, max_retries=1)
        
    duration = time.time() - start
    # 0.1 (timeout 1) + 0.5 (backoff wait) + 0.1 (timeout 2) = ~0.7 seconds total
    assert duration >= 0.6


# ==========================================
# Subscriber Async Bridging Tests
# ==========================================
@pytest.mark.asyncio
async def test_subscriber_sync_bridge(metrics):
    """
    Verifies that a developer writing a standard synchronous function
    is automatically bridged to an async background thread pool.
    """
    bus = EventBus(metrics)
    sub = EventSubscriber(bus, metrics, "sub1")
    
    received = []
    
    # Synchronous function (Intentionally blocking)
    def sync_handler(event: Event) -> None:
        received.append(event.topic)
        
    sub.subscribe("test.sync", sync_handler)
    
    e = Event(topic="test.sync", payload={})
    # Manually extract the wrapper and execute it to test the thread bridge
    wrapper = bus._subscribers["test.sync"][0]
    await wrapper(e)
    
    assert "test.sync" in received


# ==========================================
# Dispatcher Retry & DLQ Tests
# ==========================================
@pytest.mark.asyncio
async def test_dispatcher_retry_logic(metrics, queue):
    """
    Verifies that localized retry loops do not poison the master queue,
    and correctly dump to the Dead Letter Queue when exhausted.
    """
    class MockDLQ:
        def __init__(self):
            self.poisoned = []
            
        async def push(self, event, error_message):
            self.poisoned.append(event)
            
    dlq = MockDLQ()
    attempts = 0
    
    async def failing_handler(e: Event) -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("Simulated DB Crash")

    routes = {"test.fail": [failing_handler]}
    dispatcher = EventDispatcher(queue, routes, metrics, dlq, max_retries=2)
    e = Event(topic="test.fail", payload={})
    
    # Execute the handler wrapper directly
    await dispatcher._safe_execute(failing_handler, e)
    
    # Initial Attempt (1) + Retry (2) = 3 total attempts
    assert attempts == 3
    # Should be successfully routed to DLQ
    assert len(dlq.poisoned) == 1
    assert dlq.poisoned[0].topic == "test.fail"


# ==========================================
# SQLite Crash Recovery Tests
# ==========================================
@pytest.mark.asyncio
async def test_sqlite_persistence_recovery(store):
    """
    Simulates a hard process crash and verifies that PENDING events 
    are correctly recovered from the database.
    """
    e1 = Event(topic="save.1", payload={})
    e2 = Event(topic="save.2", payload={})
    
    await store.save(e1, EventStatus.PENDING)
    await store.save(e2, EventStatus.COMPLETED)
    
    recovered = await store.get_pending()
    
    assert len(recovered) == 1
    assert recovered[0].topic == "save.1"


# ==========================================
# Scheduler Chron Accuracy Tests
# ==========================================
@pytest.mark.asyncio
async def test_scheduler_recurring_execution(metrics):
    """
    Verifies that the autonomous daemon fires recurring events without drift.
    """
    bus = EventBus(metrics)
    
    # Mock the publisher to avoid needing a full EventBus queue drainer
    async def mock_publish(e: Event) -> None:
        pass
    bus.publish = mock_publish
    
    scheduler = EventScheduler(bus, metrics)
    e = Event(topic="cron.tick", payload={})
    
    # Schedule every 0.1 seconds
    scheduler.schedule_recurring(e, interval_sec=0.1)
    
    await scheduler.start()
    
    # Wait long enough for ~3 ticks to occur
    await asyncio.sleep(0.35)
    
    await scheduler.stop()
    
    # Verify the metrics engine counted the ticks
    fired_count = metrics.get_counters().get("scheduler.fired.cron.tick", 0)
    assert fired_count >= 2
