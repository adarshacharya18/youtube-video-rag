"""
EventBus compatibility module.
Re-exports EventBus and BaseEvent from src.core.events.
"""
from src.core.events.bus import BaseEvent, EventBus

Event = BaseEvent

__all__ = ["EventBus", "BaseEvent", "Event"]
