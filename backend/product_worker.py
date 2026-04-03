"""
Product worker thread — picks up parts from the shared buffer and assembles
them into finished products.

Per iteration:
  1. Generate a pickup order (PARTS_PER_PRODUCT parts from exactly 3 of 4 types,
     at least 1 of each selected type)
  2. Acquire the buffer lock and greedily retrieve whatever is available
  3. Wait (up to PRODUCT_WORKER_TIMEOUT_S) for more parts, retrieving on each wake-up
  4. After timeout, attempt one final atomic pickup if all parts are now available
  5. If order complete: increment total_products, sleep for movement + assembly time,
     broadcast "assembled"
  6. If order incomplete: discard what was collected and move to the next iteration
"""

import json
import random
import time
from typing import Callable, List

from buffer import Buffer
from event_broadcaster import EventBroadcaster
from types_def import (
    PART_ASSEMBLY_TIME_MS,
    PART_MOVEMENT_TIME_MS,
    PART_TYPES,
    PARTS_PER_PRODUCT,
    PRODUCT_WORKER_TIMEOUT_S,
)


# The four valid 3-type combinations for a pickup order
_COMBOS = [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]]


def _generate_order() -> List[int]:
    """
    Exactly PARTS_PER_PRODUCT parts drawn from exactly 3 of 4 types,
    with at least 1 part per selected type.
    """
    combo = list(random.choice(_COMBOS))
    random.shuffle(combo)
    order = [0, 0, 0, 0]
    remaining = PARTS_PER_PRODUCT
    for i, t in enumerate(combo):
        if i == len(combo) - 1:
            order[t] = remaining
        else:
            count = random.randint(1, remaining - (len(combo) - i - 1))
            order[t] = count
            remaining -= count
    return order


def _movement_ms(order: List[int]) -> float:
    return sum(order[i] * PART_MOVEMENT_TIME_MS[i] for i in range(4))


def _assembly_ms(order: List[int]) -> float:
    return sum(order[i] * PART_ASSEMBLY_TIME_MS[i] for i in range(4))


def _broadcast(
    broadcaster: EventBroadcaster,
    buffer: Buffer,
    worker_id: int,
    iteration: int,
    status: str,
    order: List[int],
    remaining: List[int],
    total_products: int,
    wait_time_ms: float = 0.0,
) -> None:
    data = {
        "worker_type": "product",
        "worker_id": worker_id,
        "iteration": iteration,
        "status": status,
        "timestamp_ms": int(time.time() * 1000),
        "wait_time_ms": int(wait_time_ms),
        "buffer_state": dict(zip(PART_TYPES, buffer.state())),
        "buffer_capacity": dict(zip(PART_TYPES, buffer.capacity())),
        "order": dict(zip(PART_TYPES, order)),
        "remaining_order": dict(zip(PART_TYPES, remaining)),
        "total_products": total_products,
    }
    broadcaster.broadcast("product_worker_event", json.dumps(data))


def run(
    worker_id: int,
    iterations: int,
    buffer: Buffer,
    broadcaster: EventBroadcaster,
    is_running: Callable[[], bool],
    counter,  # AtomicCounter from simulation.py
) -> None:
    for iteration in range(iterations):
        if not is_running():
            break

        order = _generate_order()
        remaining = list(order)
        order_complete = False

        # Critical section — hold the buffer lock for the entire pickup phase
        start = time.time()
        with buffer.pickup_cv:
            buffer.retrieve_parts(remaining)
            _broadcast(broadcaster, buffer, worker_id, iteration,
                       "new_order", order, list(remaining), counter.value())
            buffer.load_cv.notify_all()

            deadline = time.time() + PRODUCT_WORKER_TIMEOUT_S
            while sum(remaining) > 0 and is_running():
                timeout = deadline - time.time()
                if timeout <= 0:
                    break
                buffer.pickup_cv.wait(timeout)
                if not is_running():
                    break
                prev = sum(remaining)
                buffer.retrieve_parts(remaining)
                if sum(remaining) < prev:
                    _broadcast(broadcaster, buffer, worker_id, iteration,
                               "wakeup_notified", order, list(remaining),
                               counter.value(), (time.time() - start) * 1000)
                    buffer.load_cv.notify_all()

            # Final atomic attempt after timeout
            if sum(remaining) > 0 and buffer.can_fulfill_pickup(remaining):
                buffer.force_pickup(remaining)

            order_complete = sum(remaining) == 0
            wait_ms = (time.time() - start) * 1000

            if order_complete:
                tp = counter.increment()
                _broadcast(broadcaster, buffer, worker_id, iteration,
                           "completed", order, list(remaining), tp, wait_ms)
            else:
                _broadcast(broadcaster, buffer, worker_id, iteration,
                           "timeout", order, list(remaining), counter.value(), wait_ms)
            buffer.load_cv.notify_all()

        if not order_complete:
            # Parts could not be fully collected; skip assembly
            continue

        # Assembly phase (outside lock)
        time.sleep(_movement_ms(order) / 1000.0)
        if not is_running():
            break

        time.sleep(_assembly_ms(order) / 1000.0)
        if not is_running():
            break

        _broadcast(broadcaster, buffer, worker_id, iteration,
                   "assembled", order, [0, 0, 0, 0],
                   counter.value(), (time.time() - start) * 1000)
