import WorkerCard from './WorkerCard.jsx'

export default function WorkerGrid({ workers, prefix }) {
  if (workers.size === 0) {
    return <div style={{ color: 'var(--text-2)', fontSize: 11 }}>No workers yet.</div>
  }
  return (
    <div className="worker-grid">
      {[...workers.entries()].sort(([a], [b]) => a - b).map(([id, w]) => (
        <WorkerCard
          key={id}
          prefix={prefix}
          id={id}
          status={w.status}
          iteration={w.iteration}
          totalIterations={w.totalIterations}
        />
      ))}
    </div>
  )
}
