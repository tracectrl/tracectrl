export default function RiskDashboard() {
  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Risk Dashboard</h2>
        <p className="page-meta">System risk scoring, per-agent risk, and recommended actions</p>
      </div>

      <div className="empty-state">
        <div className="empty-state-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <h3>CISO Risk View</h3>
        <p>System risk score, agents at risk, critical attack paths, and recommended remediation actions — powered by TAGAAI.</p>
        <div className="sprint-tag">Sprint 2</div>
      </div>
    </div>
  )
}
