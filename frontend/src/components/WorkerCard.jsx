const STATUS_META = {
  idle:            { label: 'Idle',         color: 'var(--text-2)', glow: false },
  new_order:       { label: 'New Order',    color: 'var(--blue)',   glow: true  },
  wakeup_notified: { label: 'Notified',     color: 'var(--cyan)',   glow: true  },
  completed:       { label: 'Done ✓',       color: 'var(--green)',  glow: false },
  timeout:         { label: 'Timeout',      color: 'var(--orange)', glow: false },
  assembled:       { label: 'Assembled ✓',  color: 'var(--green)',  glow: false },
  discarded:       { label: 'Discarded',    color: 'var(--red)',    glow: false },
}

export default function WorkerCard({ prefix, id, status, iteration, totalIterations }) {
  const meta = STATUS_META[status] ?? STATUS_META.idle
  const done = status === 'completed' || status === 'assembled'

  return (
    <div className={`worker-card${meta.glow ? ' glow' : ''}`}>
      <div className="worker-id">{prefix}{id}</div>
      <div className="worker-status-row">
        <div className="status-dot" style={{ background: meta.color }} />
        <div className="worker-status-label" style={{ color: meta.color }}>
          {meta.label}
        </div>
      </div>
      {totalIterations > 0 && (
        <div className="worker-iter">
          Iter {iteration + 1}&nbsp;/&nbsp;{totalIterations}
        </div>
      )}
      {totalIterations > 0 && (
        <div className="progress-dots">
          {Array.from({ length: totalIterations }).map((_, i) => {
            let cls = 'dot'
            if (done ? i <= iteration : i < iteration) cls += ' filled'
            else if (!done && i === iteration) cls += ' half'
            return <div key={i} className={cls} />
          })}
        </div>
      )}
    </div>
  )
}
