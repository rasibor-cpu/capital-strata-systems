"""
Event Store for CSS Enterprise Event Bus

Persists events to artifacts/events/css_events.jsonl using append-only JSON lines.
Ensures thread-safe, fast writing and reading.
"""

import json
import os
import threading
from typing import Generator, Optional
from backend.events.event_models import Event
from backend.events.event_metrics import EventMetrics

class EventStore:
    def __init__(self, file_path: str = "artifacts/events/css_events.jsonl", metrics: Optional[EventMetrics] = None):
        self.file_path = file_path
        self._lock = threading.Lock()
        self._metrics = metrics

    def append(self, event: Event) -> None:
        """
        Append an event to the JSON Lines store.
        Creates parent directories automatically if they don't exist.
        """
        abs_path = os.path.abspath(self.file_path)
        dir_name = os.path.dirname(abs_path)
        
        with self._lock:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            
            event_dict = event.to_dict()
            line = json.dumps(event_dict) + "\n"
            with open(abs_path, "a", encoding="utf-8") as f:
                f.write(line)

        if self._metrics:
            self._metrics.record_persist(event)

    def read_all(self) -> Generator[Event, None, None]:
        """
        Stream events sequentially from the store.
        Yields Event objects. Skips malformed lines safely.
        """
        abs_path = os.path.abspath(self.file_path)
        if not os.path.exists(abs_path):
            return

        with self._lock:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                yield Event.from_dict(data)
            except Exception:
                continue
