"""
Shared constants for the factory simulation.
Timing values are in milliseconds and scaled 1000x from wall-clock to make
the simulation visually interesting at normal speed.
"""

NUM_PART_TYPES = 4
PART_TYPES = ['A', 'B', 'C', 'D']

# Maximum number of each part type the shared buffer can hold
BUFFER_CAPACITY = [6, 5, 4, 3]

# Time (ms) to manufacture one unit of each part type
PART_MANUFACTURE_TIME_MS = [300, 420, 540, 660]

# Time (ms) to move one unit of each part type to/from the buffer
PART_MOVEMENT_TIME_MS = [120, 180, 240, 300]

# Time (ms) to assemble one unit of each part type into a product
PART_ASSEMBLY_TIME_MS = [480, 600, 720, 840]

# How long a part worker waits for buffer space before giving up (seconds)
PART_WORKER_TIMEOUT_S = 12.0

# How long a product worker waits for parts before giving up (seconds)
PRODUCT_WORKER_TIMEOUT_S = 20.0

# Parts manufactured per load order (part worker)
PARTS_PER_LOAD_ORDER = 4

# Parts needed per product (product worker, drawn from exactly 3 types)
PARTS_PER_PRODUCT = 5
