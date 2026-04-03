"""
Factory Simulation — FastAPI + uvicorn server.

Endpoints
─────────
GET  /events            Server-Sent Events stream (one per browser tab)
POST /api/start         Start simulation  (?m=<>&n=<>&iterations=<>)
POST /api/stop          Stop simulation
GET  /api/status        Running status, product count, SSE client count
GET  /*                 Serve React build from ../frontend/dist (if present)
"""

import asyncio
import os
import sys

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from event_broadcaster import EventBroadcaster
from simulation import Simulation

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Factory Simulation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

broadcaster = EventBroadcaster()
simulation = Simulation(broadcaster)

# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    client_id = broadcaster.add_client(queue, loop)
    print(f"[SSE] Client connected (id={client_id}, "
          f"total={broadcaster.client_count()})")

    async def stream():
        try:
            yield "event: ping\ndata: connected\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {payload['event']}\ndata: {payload['data']}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: keepalive\n\n"
        finally:
            broadcaster.remove_client(client_id)
            print(f"[SSE] Client disconnected (id={client_id})")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/start")
async def api_start(
    m: int = Query(..., ge=1, le=50, description="Number of part workers"),
    n: int = Query(..., ge=1, le=50, description="Number of product workers"),
    iterations: int = Query(..., ge=1, le=20, description="Iterations per worker"),
) -> JSONResponse:
    n = min(n, m)  # product workers must not exceed part workers
    if simulation.start(m, n, iterations):
        print(f"[API] Simulation started (m={m}, n={n}, iterations={iterations})")
        return JSONResponse({"status": "started", "m": m, "n": n, "iterations": iterations})
    return JSONResponse({"error": "Simulation already running"}, status_code=409)


@app.post("/api/stop")
async def api_stop() -> JSONResponse:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, simulation.stop)
    print("[API] Simulation stopped.")
    return JSONResponse({"status": "stopped"})


@app.get("/api/status")
async def api_status() -> JSONResponse:
    return JSONResponse({
        "running": simulation.is_running(),
        "total_products": simulation.total_products(),
        "sse_clients": broadcaster.client_count(),
    })

# ---------------------------------------------------------------------------
# Static file serving (React build)
# ---------------------------------------------------------------------------

_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Factory Simulation Server  (FastAPI + uvicorn)")
    print(f"  Listening on  http://localhost:{port}")
    if os.path.isdir(_dist):
        print(f"  Serving UI from: {_dist}")
    else:
        print(f"  React build not found — run `npm run build` in frontend/")
    print()
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
