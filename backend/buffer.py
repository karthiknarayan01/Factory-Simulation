"""
Thread-safe shared buffer between part workers (producers) and product workers
(consumers).

Both condition variables share the same underlying lock, matching the C++ design
where a single std::mutex guards two std::condition_variables.

  load_cv   — part workers wait here when the buffer is full
  pickup_cv — product workers wait here when parts are unavailable

Operations that modify buffer state must be called while holding the lock
(i.e., inside `with buffer.load_cv:` or `with buffer.pickup_cv:`).
"""

import threading
from typing import List

from types_def import BUFFER_CAPACITY


class Buffer:
    def __init__(self) -> None:
        self._state: List[int] = [0, 0, 0, 0]
        self._capacity: List[int] = list(BUFFER_CAPACITY)

        # Single lock shared by both conditions
        self._lock = threading.Lock()
        self._load_cv = threading.Condition(self._lock)
        self._pickup_cv = threading.Condition(self._lock)

    # ------------------------------------------------------------------ #
    # Read-only queries (call while holding the lock)                      #
    # ------------------------------------------------------------------ #

    def state(self) -> List[int]:
        """Returns a snapshot of current part counts."""
        return list(self._state)

    def capacity(self) -> List[int]:
        """Returns the per-type capacity limits."""
        return list(self._capacity)

    # ------------------------------------------------------------------ #
    # Greedy partial operations (call while holding the lock)              #
    # ------------------------------------------------------------------ #

    def deposit_parts(self, remaining: List[int]) -> None:
        """
        Deposits as many parts as possible from `remaining` into the buffer.
        Modifies `remaining` in-place to reflect undeposited quantities.
        """
        for i in range(4):
            space = self._capacity[i] - self._state[i]
            deposited = min(space, remaining[i])
            self._state[i] += deposited
            remaining[i] -= deposited

    def retrieve_parts(self, remaining: List[int]) -> None:
        """
        Retrieves as many parts as available from `remaining`.
        Modifies `remaining` in-place to reflect quantities still needed.
        """
        for i in range(4):
            retrieved = min(self._state[i], remaining[i])
            self._state[i] -= retrieved
            remaining[i] -= retrieved

    # ------------------------------------------------------------------ #
    # Atomic all-or-nothing checks (call while holding the lock)           #
    # ------------------------------------------------------------------ #

    def can_fulfill_deposit(self, order: List[int]) -> bool:
        """True if every part in `order` fits without exceeding capacity."""
        return all(order[i] <= self._capacity[i] - self._state[i] for i in range(4))

    def can_fulfill_pickup(self, order: List[int]) -> bool:
        """True if every part in `order` is currently available."""
        return all(order[i] <= self._state[i] for i in range(4))

    def force_deposit(self, order: List[int]) -> None:
        """Atomically deposits all parts and zeros out `order`. Call only after
        verifying with `can_fulfill_deposit`."""
        for i in range(4):
            self._state[i] += order[i]
            order[i] = 0

    def force_pickup(self, order: List[int]) -> None:
        """Atomically retrieves all parts and zeros out `order`. Call only after
        verifying with `can_fulfill_pickup`."""
        for i in range(4):
            self._state[i] -= order[i]
            order[i] = 0

    # ------------------------------------------------------------------ #
    # Condition variable accessors                                         #
    # ------------------------------------------------------------------ #

    @property
    def load_cv(self) -> threading.Condition:
        """Condition variable for part workers (wait for buffer space)."""
        return self._load_cv

    @property
    def pickup_cv(self) -> threading.Condition:
        """Condition variable for product workers (wait for parts)."""
        return self._pickup_cv

    # ------------------------------------------------------------------ #
    # Shutdown                                                             #
    # ------------------------------------------------------------------ #

    def notify_all(self) -> None:
        """Wake every thread blocked on either condition (used during stop)."""
        with self._load_cv:          # acquires shared lock
            self._load_cv.notify_all()
            self._pickup_cv.notify_all()  # same lock, safe to notify both
