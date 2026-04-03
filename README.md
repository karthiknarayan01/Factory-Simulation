# Factory Simulation

A real-time factory simulation with a live browser dashboard. The backend models a multi-threaded production floor — part workers manufacturing and depositing parts into a shared buffer, and product workers retrieving those parts and assembling finished goods. Every event that occurs on the factory floor is streamed to the browser as it happens.

---

## What it simulates

The factory has two types of workers, each running as its own thread:

**Part workers** manufacture parts of four types (A, B, C, D) and deposit them into a shared buffer. The buffer has a fixed capacity per part type (6, 5, 4, 3 respectively). When the buffer is full for a needed type, the worker waits up to 12 seconds for space to open before discarding any unloaded parts.

**Product workers** pull parts from the buffer and assemble products. Each product requires exactly 5 parts drawn from exactly 3 of the 4 part types. Workers wait up to 20 seconds for the required parts. If they can collect everything in time, they assemble a product; otherwise they discard what they collected.

Access to the shared buffer is serialised with a lock and two condition variables — one that wakes part workers when buffer space opens up, and one that wakes product workers when new parts are deposited. This ensures fair, race-free access across all threads.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3, [FastAPI](https://fastapi.tiangolo.com/), [uvicorn](https://www.uvicorn.org/) |
| Threading | Python `threading` — `Lock` + two `Condition` variables |
| Event delivery | Server-Sent Events (SSE) via `StreamingResponse` |
| Frontend | [React 18](https://react.dev/) + [Vite](https://vitejs.dev/) |

---

## Project structure

```
Factory-Simulation/
├── backend/
│   ├── main.py              # FastAPI app — API routes, SSE endpoint, static file serving
│   ├── simulation.py        # Lifecycle controller (start / stop / monitor thread)
│   ├── buffer.py            # Shared buffer with Lock + two Conditions (load_cv, pickup_cv)
│   ├── part_worker.py       # Part-worker thread logic
│   ├── product_worker.py    # Product-worker thread logic
│   ├── event_broadcaster.py # Distributes SSE events to all connected browser clients
│   ├── types_def.py         # Shared constants (timing, capacities, counts)
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx              # Root component — SSE connection, all simulation state
    │   ├── App.css              # Dark industrial theme, gauge + badge animations
    │   └── components/
    │       ├── BufferGauges.jsx # Animated vertical bars per part type (A, B, C, D)
    │       ├── WorkerCard.jsx   # Status dot, progress dots, per-worker card
    │       ├── WorkerGrid.jsx   # Responsive grid of worker cards
    │       └── ActivityFeed.jsx # Scrollable real-time event log
    ├── package.json
    ├── vite.config.js           # Dev proxy: /api and /events → localhost:8080
    └── index.html
```

---

## Running

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

The server starts on **http://localhost:8080**. If a React production build exists at `frontend/dist/`, it is served automatically.

### 2. Frontend

**Development** (hot-reload, proxies API calls to the backend):

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**.

**Production build** (served by the backend at port 8080):

```bash
cd frontend
npm run build
# Now just open http://localhost:8080
```

---

## Using the dashboard

1. **Configure** the number of part workers (m), product workers (n ≤ m), and iterations per worker using the inputs in the header.
2. Click **Start** to launch the simulation. Worker cards appear for each thread, and the shared buffer gauges animate in real time.
3. Watch the **buffer gauges** fill and drain as part workers deposit and product workers retrieve parts.
4. Each **worker card** shows the worker's current status, which iteration it is on, and a colour-coded indicator:
   - Blue — loading / picking up parts
   - Cyan — woken by a condition-variable notification
   - Orange — timed out
   - Green — product assembled successfully
   - Red — parts discarded
5. The **Activity Feed** on the right logs every significant event in real time.
6. Click **Stop** at any time to gracefully halt all threads.

The simulation ends automatically when every worker completes its iterations. The total products manufactured is displayed in the header.

---

## Simulation parameters

| Parameter | Default | Notes |
|---|---|---|
| Part workers (m) | 5 | Max 50 |
| Product workers (n) | 3 | Must be ≤ m |
| Iterations per worker | 5 | Max 20 |
| Part-worker timeout | 12 000 ms | Defined in `types_def.py` |
| Product-worker timeout | 20 000 ms | Defined in `types_def.py` |
| Buffer capacity | (6, 5, 4, 3) | Per part type A, B, C, D |

> **Timing note:** All timing values are in milliseconds, scaled 1000× from the original specification so the simulation runs for a human-observable 10–30 seconds.
