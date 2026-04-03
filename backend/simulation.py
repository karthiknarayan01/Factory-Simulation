"""
Simulation — lifecycle orchestrator.

start(m, n, iterations)
  Validates parameters, resets shared state, launches m part-worker threads
  and n product-worker threads, then launches a monitor thread that joins
  them all and broadcasts the final simulation_event when they finish.

stop()
  Signals workers to exit, wakes all blocked threads via buffer.notify_all(),
  and waits for the monitor thread to finish (which in turn joins the workers).

Thread safety
  A control lock prevents concurrent start()/stop() calls.
  is_running is a threading.Event; workers check is_running.is_set().
  total_products is protected by AtomicCounter (its own lock).
"""

import json
import threading
from typing import List, Optional

import part_worker as pw
import product_worker as qw
from buffer import Buffer
from event_broadcaster import EventBroadcaster


class _AtomicCounter:
    def __init__(self) -> None:
        self._v = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._v += 1
            return self._v

    def value(self) -> int:
        with self._lock:
            return self._v

    def reset(self) -> None:
        with self._lock:
            self._v = 0


class Simulation:
    def __init__(self, broadcaster: EventBroadcaster) -> None:
        self._broadcaster = broadcaster
        self._buffer: Optional[Buffer] = None
        self._is_running = threading.Event()
        self._stop_requested = False
        self._counter = _AtomicCounter()
        self._threads: List[threading.Thread] = []
        self._monitor: Optional[threading.Thread] = None
        self._ctrl_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self, m: int, n: int, iterations: int) -> bool:
        """
        Launch m part workers and n product workers for `iterations` rounds.
        Returns False if a simulation is already running.
        """
        with self._ctrl_lock:
            if self._is_running.is_set():
                return False

            # Reset shared state
            self._buffer = Buffer()
            self._stop_requested = False
            self._counter.reset()
            self._threads = []

            self._is_running.set()

            self._broadcaster.broadcast(
                "simulation_event",
                json.dumps({
                    "type": "started",
                    "num_part_workers": m,
                    "num_product_workers": n,
                    "total_products": 0,
                }),
            )

            # Product workers (IDs 0..n-1)
            for i in range(n):
                t = threading.Thread(
                    target=qw.run,
                    args=(i, iterations, self._buffer, self._broadcaster,
                          self._is_running.is_set, self._counter),
                    daemon=True,
                    name=f"product-{i}",
                )
                self._threads.append(t)

            # Part workers (IDs 0..m-1)
            for i in range(m):
                t = threading.Thread(
                    target=pw.run,
                    args=(i, iterations, self._buffer, self._broadcaster,
                          self._is_running.is_set),
                    daemon=True,
                    name=f"part-{i}",
                )
                self._threads.append(t)

            for t in self._threads:
                t.start()

            self._monitor = threading.Thread(
                target=self._monitor_workers,
                args=(m, n),
                daemon=True,
                name="monitor",
            )
            self._monitor.start()

            return True

    def stop(self) -> None:
        """Signal workers to exit and wait for them to finish."""
        with self._ctrl_lock:
            if not self._is_running.is_set():
                return
            self._stop_requested = True
            self._is_running.clear()
            if self._buffer:
                self._buffer.notify_all()

        if self._monitor:
            self._monitor.join()

    def is_running(self) -> bool:
        return self._is_running.is_set()

    def total_products(self) -> int:
        return self._counter.value()

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _monitor_workers(self, m: int, n: int) -> None:
        """Joins all worker threads, then broadcasts the final lifecycle event."""
        for t in self._threads:
            t.join()

        self._is_running.clear()

        event_type = "stopped" if self._stop_requested else "complete"
        self._broadcaster.broadcast(
            "simulation_event",
            json.dumps({
                "type": event_type,
                "num_part_workers": m,
                "num_product_workers": n,
                "total_products": self._counter.value(),
            }),
        )
