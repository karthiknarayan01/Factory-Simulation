export default function ActivityFeed({ entries, onClear }) {
  return (
    <>
      <div className="feed-header">
        <span className="panel-title" style={{ borderBottom: 'none', paddingBottom: 0 }}>
          Activity Log
        </span>
        <button className="btn btn-clear" onClick={onClear}>Clear</button>
      </div>
      <div className="feed-scroll">
        {entries.map(e => (
          <div className="feed-entry" key={e.id}>
            <span className="feed-ts">{e.ts}s</span>
            <span className="feed-who" style={{ color: e.color }}>{e.workerId}</span>
            <span className="feed-msg">{e.message}</span>
          </div>
        ))}
        {entries.length === 0 && (
          <div style={{ color: 'var(--text-2)', fontSize: 11, padding: '4px 6px' }}>
            Waiting for events…
          </div>
        )}
      </div>
    </>
  )
}
