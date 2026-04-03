import { useEffect, useRef, useState } from 'react'
import BufferGauges from './components/BufferGauges.jsx'
import WorkerGrid from './components/WorkerGrid.jsx'
import ActivityFeed from './components/ActivityFeed.jsx'

const LOG_FILTER = new Set(['new_order', 'completed', 'timeout', 'assembled'])
const MAX_LOG = 300

// ── Helpers ──────────────────────────────────────────────────────────────

function fmtElapsed(startMs) {
  const secs = Math.floor((Date.now() - startMs) / 1000)
  return `${Math.floor(secs / 60)}:${(secs % 60).toString().padStart(2, '0')}`
}

function orderStr(obj) {
  return Object.entries(obj).filter(([, v]) => v > 0).map(([k, v]) => `${v}${k}`).join(', ') || 'none'
}

function partMsg(data) {
  switch (data.status) {
    case 'new_order':
      return `Load [${orderStr(data.order)}] → deposited, still need: [${orderStr(data.remaining_order)}]`
    case 'completed':
      return `All parts deposited ✓`
    case 'timeout':
      return `Timeout — discarded: [${orderStr(data.remaining_order)}]`
    default:
      return data.status
  }
}

function productMsg(data) {
  switch (data.status) {
    case 'new_order':
      return `Pickup [${orderStr(data.order)}] → got some, still need: [${orderStr(data.remaining_order)}]`
    case 'completed':
      return `Parts collected, assembling [${orderStr(data.order)}]`
    case 'timeout':
      return `Timeout — could not collect [${orderStr(data.remaining_order)}]`
    case 'assembled':
      return `Product assembled! [${orderStr(data.order)}] → total: ${data.total_products}`
    default:
      return data.status
  }
}

const STATUS_COLOR = {
  idle: 'var(--text-2)',
  new_order: 'var(--blue)',
  wakeup_notified: 'var(--cyan)',
  completed: 'var(--green)',
  timeout: 'var(--orange)',
  assembled: 'var(--green)',
  discarded: 'var(--red)',
}

// ── App ───────────────────────────────────────────────────────────────────

export default function App() {
  const [m, setM] = useState(5)
  const [n, setN] = useState(3)
  const [iters, setIters] = useState(5)

  const [simStatus, setSimStatus] = useState('idle')   // idle | running | complete | stopped
  const [elapsed, setElapsed] = useState('0:00')
  const [eventCount, setEventCount] = useState(0)
  const [productCount, setProductCount] = useState(0)

  const [bufferState, setBufferState] = useState({ A: 0, B: 0, C: 0, D: 0 })
  const [partWorkers, setPartWorkers] = useState(new Map())
  const [productWorkers, setProductWorkers] = useState(new Map())
  const [activityLog, setActivityLog] = useState([])

  // Refs for values needed inside the stable SSE closure
  const simStartRef = useRef(null)
  const elapsedTimerRef = useRef(null)
  const configuredItersRef = useRef(5)

  // Keep configuredItersRef in sync
  useEffect(() => { configuredItersRef.current = iters }, [iters])

  // ── SSE connection (set up once) ────────────────────────────────────────
  useEffect(() => {
    const es = new EventSource('/events')

    // ── Helpers used inside handlers ──
    const addLog = (entry) => {
      setActivityLog(prev => {
        const next = [entry, ...prev]
        return next.length > MAX_LOG ? next.slice(0, MAX_LOG) : next
      })
    }

    const ts = () =>
      simStartRef.current != null
        ? ((Date.now() - simStartRef.current) / 1000).toFixed(1)
        : '0.0'

    const updateBuffer = (bs) => {
      if (bs) setBufferState({ A: bs.A ?? 0, B: bs.B ?? 0, C: bs.C ?? 0, D: bs.D ?? 0 })
    }

    // ── part_worker_event ─────────────────────────────────────────────────
    es.addEventListener('part_worker_event', (e) => {
      const d = JSON.parse(e.data)
      updateBuffer(d.buffer_state)
      setPartWorkers(prev => {
        const next = new Map(prev)
        next.set(d.worker_id, {
          status: d.status,
          iteration: d.iteration,
          totalIterations: configuredItersRef.current,
        })
        return next
      })
      if (LOG_FILTER.has(d.status)) {
        setEventCount(c => c + 1)
        addLog({
          id: Date.now() + Math.random(),
          ts: ts(),
          workerId: `P${d.worker_id}`,
          message: partMsg(d),
          color: STATUS_COLOR[d.status] ?? 'var(--text-1)',
        })
      }
    })

    // ── product_worker_event ──────────────────────────────────────────────
    es.addEventListener('product_worker_event', (e) => {
      const d = JSON.parse(e.data)
      updateBuffer(d.buffer_state)
      setProductWorkers(prev => {
        const next = new Map(prev)
        next.set(d.worker_id, {
          status: d.status,
          iteration: d.iteration,
          totalIterations: configuredItersRef.current,
        })
        return next
      })
      if (d.total_products != null) setProductCount(d.total_products)
      if (LOG_FILTER.has(d.status)) {
        setEventCount(c => c + 1)
        addLog({
          id: Date.now() + Math.random(),
          ts: ts(),
          workerId: `Q${d.worker_id}`,
          message: productMsg(d),
          color: STATUS_COLOR[d.status] ?? 'var(--text-1)',
        })
      }
    })

    // ── simulation_event ──────────────────────────────────────────────────
    es.addEventListener('simulation_event', (e) => {
      const d = JSON.parse(e.data)

      if (d.type === 'started') {
        setSimStatus('running')
        setProductCount(0)
        setEventCount(0)
        setBufferState({ A: 0, B: 0, C: 0, D: 0 })
        simStartRef.current = Date.now()
        setElapsed('0:00')

        if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
        elapsedTimerRef.current = setInterval(() => {
          setElapsed(fmtElapsed(simStartRef.current))
        }, 1000)

        setPartWorkers(() => {
          const mp = new Map()
          for (let i = 0; i < d.num_part_workers; i++)
            mp.set(i, { status: 'idle', iteration: 0, totalIterations: configuredItersRef.current })
          return mp
        })
        setProductWorkers(() => {
          const mp = new Map()
          for (let i = 0; i < d.num_product_workers; i++)
            mp.set(i, { status: 'idle', iteration: 0, totalIterations: configuredItersRef.current })
          return mp
        })
        setActivityLog([{
          id: Date.now(),
          ts: '0.0',
          workerId: 'SIM',
          message: `Started: ${d.num_part_workers} part workers, ${d.num_product_workers} product workers`,
          color: 'var(--blue)',
        }])

      } else if (d.type === 'complete' || d.type === 'stopped') {
        setSimStatus(d.type === 'complete' ? 'complete' : 'stopped')
        if (elapsedTimerRef.current) {
          clearInterval(elapsedTimerRef.current)
          elapsedTimerRef.current = null
        }
        setProductCount(d.total_products)
        const color = d.type === 'complete' ? 'var(--green)' : 'var(--orange)'
        const msg = d.type === 'complete'
          ? `Simulation complete — ${d.total_products} products assembled`
          : `Simulation stopped — ${d.total_products} products assembled`
        addLog({ id: Date.now(), ts: ts(), workerId: 'SIM', message: msg, color })
      }
    })

    es.onerror = () => console.warn('[SSE] connection error')

    return () => {
      es.close()
      if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Actions ───────────────────────────────────────────────────────────
  const startSim = async () => {
    const clampedN = Math.min(n, m)
    try {
      const r = await fetch(`/api/start?m=${m}&n=${clampedN}&iterations=${iters}`, { method: 'POST' })
      if (r.status === 409) { alert('Simulation is already running.'); return }
      if (!r.ok) { alert('Failed to start simulation.'); return }
      configuredItersRef.current = iters
    } catch {
      alert('Backend not reachable. Is the server running?')
    }
  }

  const stopSim = async () => {
    try { await fetch('/api/stop', { method: 'POST' }) }
    catch { console.error('stop failed') }
  }

  const clearLog = () => {
    setActivityLog([])
    setEventCount(0)
  }

  const simRunning = simStatus === 'running'

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <span className="header-logo">⚙ Factory Simulation</span>
        <span className={`status-badge ${simStatus}`}>
          {simStatus === 'idle' ? 'Idle'
            : simStatus === 'running' ? 'Running'
            : simStatus === 'complete' ? 'Complete'
            : 'Stopped'}
        </span>

        <div className="header-stats">
          <div className="stat-pill">Products<span>{productCount}</span></div>
          <div className="stat-pill">Events<span>{eventCount}</span></div>
          <div className="stat-pill">Elapsed<span>{elapsed}</span></div>
        </div>

        <div className="header-controls">
          <div className="ctrl-group">
            <label>Part workers (m)</label>
            <input type="number" min={1} max={50} value={m}
              onChange={e => setM(Math.max(1, Math.min(50, +e.target.value)))} disabled={simRunning} />
          </div>
          <div className="ctrl-group">
            <label>Product workers (n)</label>
            <input type="number" min={1} max={50} value={n}
              onChange={e => setN(Math.max(1, Math.min(50, +e.target.value)))} disabled={simRunning} />
          </div>
          <div className="ctrl-group">
            <label>Iterations</label>
            <input type="number" min={1} max={20} value={iters}
              onChange={e => setIters(Math.max(1, Math.min(20, +e.target.value)))} disabled={simRunning} />
          </div>
          <button className="btn btn-start" onClick={startSim} disabled={simRunning}>Start</button>
          <button className="btn btn-stop"  onClick={stopSim}  disabled={!simRunning}>Stop</button>
        </div>
      </header>

      {/* Main content */}
      <main className="main">
        {/* Left panel */}
        <div>
          <div className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-title">Buffer State</div>
            <BufferGauges bufferState={bufferState} />
          </div>

          <div className="panel">
            <div className="panel-title">Part Workers ({partWorkers.size})</div>
            <WorkerGrid workers={partWorkers} prefix="P" />
          </div>
        </div>

        {/* Right panel */}
        <div>
          <div className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-title">Product Workers ({productWorkers.size})</div>
            <WorkerGrid workers={productWorkers} prefix="Q" />
          </div>

          <div className="panel">
            <ActivityFeed entries={activityLog} onClear={clearLog} />
          </div>
        </div>
      </main>
    </div>
  )
}
