"""
Part worker thread — manufactures a random load of parts and deposits them into
the shared buffer, waiting if there is not enough space.

Per iteration:
  1. Generate a random load order (PARTS_PER_LOAD_ORDER parts, shuffled across types)
  2. Sleep to simulate manufacturing time
  3. Sleep to simulate travel time to the buffer
  4. Acquire the buffer lock and greedily deposit whatever fits
  5. Wait (up to PART_WORKER_TIMEOUT_S) for space to open, depositing on each wake-up
  6. After timeout, attempt one final atomic deposit if space is now available
  7. Broadcast the final status and discard any remaining parts
"""

import json
import random
import time
from typing import Callable, List

from buffer import Buffer
from event_broadcaster import EventBroadcaster
from types_def import (
    BUFFER_CAPACITY,
    PART_MOVEMENT_TIME_MS,
    PART_MANUFACTURE_TIME_MS,
    PART_TYPES,
    PART_WORKER_TIMEOUT_S,
    PARTS_PER_LOAD_ORDER,
)


def _generate_order() -> List[int]:
    """
    Random allocation of PARTS_PER_LOAD_ORDER parts across the four types.
    The type order is shuffled to prevent systematic bias toward type A.
    Some types may receive zero parts.
    """
    order = [0, 0, 0, 0]
    types = list(range(4))
    random.shuffle(types)
    remaining = PARTS_PER_LOAD_ORDER
    for i, t in enumerate(types):
        if i == len(types) - 1:
            order[t] = remaining
        else:
            count = random.randint(0, remaining)
            order[t] = count
            remaining -= count
            if remaining == 0:
                break
    return order


def _manufacture_ms(order: List[int]) -> float:
    return sum(order[i] * PART_MANUFACTURE_TIME_MS[i] for i in range(4))


def _movement_ms(order: List[int]) -> float:
    return sum(order[i] * PART_MOVEMENT_TIME_MS[i] for i in range(4))


def _broadcast(
    broadcaster: EventBroadcaster,
    buffer: Buffer,
    worker_id: int,
    iteration: int,
    status: str,
    order: List[int],
    remaining: List[int],
    wait_time_ms: float = 0.0,
) -> None:
    data = {
        "worker_type": "part",
        "worker_id": worker_id,
        "iteration": iteration,
        "status": status,
        "timestamp_ms": int(time.time() * 1000),
        "wait_time_ms": int(wait_time_ms),
        "buffer_state": dict(zip(PART_TYPES, buffer.state())),
        "buffer_capacity": dict(zip(PART_TYPES, buffer.capacity())),
        "order": dict(zip(PART_TYPES, order)),
        "remaining_order": dict(zip(PART_TYPES, remaining)),
    }
    broadcaster.broadcast("part_worker_event", json.dumps(data))


def run(
    worker_id: int,
    iterations: int,
    buffer: Buffer,
    broadcaster: EventBroadcaster,
    is_running: Callable[[], bool],
) -> None:
    for iteration in range(iterations):
        if not is_running():
            break

        order = _generate_order()
        remaining = list(order)

        # Manufacture
        time.sleep(_manufacture_ms(order) / 1000.0)
        if not is_running():
            break

        # Travel to buffer
        time.sleep(_movement_ms(order) / 1000.0)
        if not is_running():
            break

        # Critical section — hold the buffer lock for the entire deposit phase
        start = time.time()
        with buffer.load_cv:
            buffer.deposit_parts(remaining)
            _broadcast(broadcaster, buffer, worker_id, iteration,
                       "new_order", order, list(remaining))
            buffer.pickup_cv.notify_all()

            deadline = time.time() + PART_WORKER_TIMEOUT_S
            while sum(remaining) > 0 and is_running():
                timeout = deadline - time.time()
                if timeout <= 0:
                    break
                buffer.load_cv.wait(timeout)
                if not is_running():
                    break
                prev = sum(remaining)
                buffer.deposit_parts(remaining)
                if sum(remaining) < prev:
                    _broadcast(broadcaster, buffer, worker_id, iteration,
                               "wakeup_notified", order, list(remaining),
                               (time.time() - start) * 1000)
                    buffer.pickup_cv.notify_all()

            # Final atomic attempt after timeout
            if sum(remaining) > 0 and buffer.can_fulfill_deposit(remaining):
                buffer.force_deposit(remaining)

            wait_ms = (time.time() - start) * 1000
            status = "completed" if sum(remaining) == 0 else "timeout"
            _broadcast(broadcaster, buffer, worker_id, iteration,
                       status, order, list(remaining), wait_ms)
            buffer.pickup_cv.notify_all()

        # Discard any parts that could not be deposited
        if sum(remaining) > 0:
            time.sleep(_movement_ms(remaining) / 1000.0)
