import { BrowserRouter, Routes, Route, Navigate, useLocation, Link } from 'react-router-dom'
import TopologyGraph from './pages/TopologyGraph'
import Sessions from './pages/Sessions'
import Agents from './pages/Agents'
import TraceDetail from './pages/TraceDetail'
import RiskDashboard from './pages/RiskDashboard'
import AttackPaths from './pages/AttackPaths'
import { ProjectProvider, useProject } from './context/ProjectContext'

function Sidebar() {
  const location = useLocation()
  const { projects, selectedProject, setSelectedProject, loading: projectsLoading } = useProject()

  const navItems = [
    { href: '/topology', label: 'Topology' },
    { href: '/sessions', label: 'Sessions' },
    { href: '/agents', label: 'Agents' },
    { href: '/risk', label: 'Risk Dashboard' },
    { href: '/attacks', label: 'Attack Paths' },
  ]

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <h1><span className="logo-trace">trace</span><span className="logo-ctrl">ctrl</span></h1>
        <div className="subtitle">Security Observability</div>
      </div>

      <div className="sidebar-project-selector">
        <label className="sidebar-project-label">Project</label>
        <select
          className="sidebar-project-select"
          value={selectedProject || ''}
          onChange={e => setSelectedProject(e.target.value || null)}
          disabled={projectsLoading}
        >
          <option value="">All Projects</option>
          {projects.map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div className="sidebar-section-label">Monitor</div>
      {navItems.slice(0, 3).map(item => (
        <Link
          key={item.href}
          to={item.href}
          className={`nav-link${location.pathname === item.href || location.pathname.startsWith(item.href + '/') ? ' active' : ''}`}
        >
          {item.label}
        </Link>
      ))}

      <div className="sidebar-section-label">Security</div>
      {navItems.slice(3).map(item => (
        <Link
          key={item.href}
          to={item.href}
          className={`nav-link${location.pathname === item.href || location.pathname.startsWith(item.href + '/') ? ' active' : ''}`}
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
      <ProjectProvider>
        <div className="layout">
          <Sidebar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Navigate to="/topology" replace />} />
              <Route path="/topology" element={<TopologyGraph />} />
              <Route path="/sessions" element={<Sessions />} />
              <Route path="/sessions/:traceId" element={<TraceDetail />} />
              <Route path="/agents" element={<Agents />} />
              <Route path="/risk" element={<RiskDashboard />} />
              <Route path="/attacks" element={<AttackPaths />} />
            </Routes>
          </main>
        </div>
      </ProjectProvider>
    </BrowserRouter>
  )
}

export default App
