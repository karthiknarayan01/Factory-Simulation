import { useEffect, useRef, useState } from 'react'

const TYPE_COLORS = {
  A: 'var(--type-a)',
  B: 'var(--type-b)',
  C: 'var(--type-c)',
  D: 'var(--type-d)',
}

const CAPACITY = { A: 6, B: 5, C: 4, D: 3 }

function Gauge({ type, current, capacity }) {
  const [flashing, setFlashing] = useState(false)
  const prevRef = useRef(current)
  const timerRef = useRef(null)

  useEffect(() => {
    if (prevRef.current !== current) {
      prevRef.current = current
      if (timerRef.current) clearTimeout(timerRef.current)
      setFlashing(true)
      timerRef.current = setTimeout(() => setFlashing(false), 420)
    }
  }, [current])

  const pct = capacity > 0 ? (current / capacity) * 100 : 0

  return (
    <div className="gauge-wrap">
      <div className="gauge-label-top" style={{ color: TYPE_COLORS[type] }}>{type}</div>
      <div className="gauge-track">
        <div
          className={`gauge-fill${flashing ? ' flash' : ''}`}
          style={{ height: `${pct}%`, backgroundColor: TYPE_COLORS[type] }}
        />
      </div>
      <div className="gauge-count">{current}&nbsp;/&nbsp;{capacity}</div>
    </div>
  )
}

export default function BufferGauges({ bufferState }) {
  return (
    <div className="buffer-gauges">
      {['A', 'B', 'C', 'D'].map(t => (
        <Gauge
          key={t}
          type={t}
          current={bufferState[t] ?? 0}
          capacity={CAPACITY[t]}
        />
      ))}
    </div>
  )
}
