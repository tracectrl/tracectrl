export default function Sessions() {
  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Monitor</div>
        <h2>Sessions</h2>
        <p className="page-meta">Trace explorer for agent sessions and span trees</p>
      </div>

      <div className="empty-state">
        <div className="empty-state-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
        </div>
        <h3>Session Explorer</h3>
        <p>Paginated session list with full span trees — every LLM call, tool call, and agent-to-agent message in chronological order.</p>
        <div className="sprint-tag">Sprint 2</div>
      </div>
    </div>
  )
}
