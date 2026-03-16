import { BrowserRouter, Routes, Route, Navigate, useLocation, Link } from 'react-router-dom'
import TopologyGraph from './pages/TopologyGraph'
import Sessions from './pages/Sessions'
import RiskDashboard from './pages/RiskDashboard'
import AttackPaths from './pages/AttackPaths'

function Sidebar() {
  const location = useLocation()

  const navItems = [
    { href: '/topology', label: 'Topology' },
    { href: '/sessions', label: 'Sessions' },
    { href: '/risk', label: 'Risk Dashboard' },
    { href: '/attacks', label: 'Attack Paths' },
  ]

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <h1>Trace<span className="accent">Ctrl</span></h1>
        <div className="subtitle">Security Observability</div>
      </div>

      <div className="sidebar-section-label">Monitor</div>
      {navItems.slice(0, 2).map(item => (
        <Link
          key={item.href}
          to={item.href}
          className={`nav-link${location.pathname === item.href ? ' active' : ''}`}
        >
          {item.label}
        </Link>
      ))}

      <div className="sidebar-section-label">Security</div>
      {navItems.slice(2).map(item => (
        <Link
          key={item.href}
          to={item.href}
          className={`nav-link${location.pathname === item.href ? ' active' : ''}`}
        >
          {item.label}
        </Link>
      ))}

      <div className="sidebar-footer">
        <p>TraceCtrl v0.1.0</p>
        <p>by CloudsineAI</p>
      </div>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/topology" replace />} />
            <Route path="/topology" element={<TopologyGraph />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/risk" element={<RiskDashboard />} />
            <Route path="/attacks" element={<AttackPaths />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
