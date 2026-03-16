export default function AttackPaths() {
  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Attack Paths</h2>
        <p className="page-meta">Ranked exploitation chains from TAGAAI attack graph analysis</p>
      </div>

      <div className="empty-state">
        <div className="empty-state-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>
        <h3>Attack Path Analysis</h3>
        <p>Ranked attack paths with OWASP ASI mapping, step-by-step exploitation chains, and risk scores for every path an adversary could take.</p>
        <div className="sprint-tag">Sprint 2</div>
      </div>
    </div>
  )
}
