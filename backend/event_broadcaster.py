"""
EventBroadcaster — delivers SSE payloads from simulation worker threads to all
connected browser clients without blocking the workers.

Design
──────
Each SSE client registers an asyncio.Queue plus the event loop it lives on.
When broadcast() is called from a worker thread it uses loop.call_soon_threadsafe
to schedule queue.put_nowait on the event loop thread — a non-blocking,
thread-safe handoff. The async SSE generator on the other end simply awaits
items from the queue.
"""

import asyncio
import threading
from typing import Dict, Tuple


class EventBroadcaster:
    def __init__(self) -> None:
        self._clients: Dict[int, Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = {}
        self._lock = threading.Lock()
        self._next_id = 0

    def add_client(
        self,
        queue: "asyncio.Queue[dict]",
        loop: asyncio.AbstractEventLoop,
    ) -> int:
        """Register a new SSE client. Returns a client_id for later removal."""
        with self._lock:
            cid = self._next_id
            self._next_id += 1
            self._clients[cid] = (queue, loop)
            return cid

    def remove_client(self, cid: int) -> None:
        """Unregister an SSE client (called when the browser disconnects)."""
        with self._lock:
            self._clients.pop(cid, None)

    def broadcast(self, event_type: str, data: str) -> None:
        """
        Deliver an SSE message to every connected client.
        Safe to call from any thread; never blocks.
        """
        payload = {"event": event_type, "data": data}
        with self._lock:
            clients = list(self._clients.values())
        for queue, loop in clients:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, payload)
            except Exception:
                pass  # client may have just disconnected

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)
