import json
import threading
from typing import List, Dict, Any

class TelemetryBuffer:
    def __init__(self, max_mb: int = 20):
        self.max_bytes = max_mb * 1024 * 1024
        self.lock = threading.Lock()
        self.queue: List[Dict[str, Any]] = []
        self.estimated_bytes = 0

    def push(self, snapshot: Dict[str, Any]):
        with self.lock:
            # Estimate size
            try:
                raw = json.dumps(snapshot)
                item_size = len(raw.encode("utf-8"))
            except Exception:
                item_size = 1024 # estimate 1 KB

            # Drop oldest first if buffer full
            while self.queue and (self.estimated_bytes + item_size) > self.max_bytes:
                dropped = self.queue.pop(0)
                try:
                    dropped_size = len(json.dumps(dropped).encode("utf-8"))
                except Exception:
                    dropped_size = 1024
                self.estimated_bytes = max(0, self.estimated_bytes - dropped_size)

            self.queue.append(snapshot)
            self.estimated_bytes += item_size

    def pop_all(self) -> List[Dict[str, Any]]:
        with self.lock:
            batch = list(self.queue)
            self.queue.clear()
            self.estimated_bytes = 0
            return batch

    def restore_batch(self, batch: List[Dict[str, Any]]):
        """Prepend batch back to front if network transmission failed."""
        with self.lock:
            self.queue = batch + self.queue
            self.estimated_bytes = sum(len(json.dumps(x).encode("utf-8")) for x in self.queue)

    def size(self) -> int:
        with self.lock:
            return len(self.queue)
