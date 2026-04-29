import { BrowserRouter, Routes, Route, Navigate, useLocation, Link } from 'react-router-dom'
import TopologyGraph from './pages/TopologyGraph'
import Sessions from './pages/Sessions'
import Agents from './pages/Agents'
import TraceDetail from './pages/TraceDetail'
import RiskDashboard from './pages/RiskDashboard'
import AttackPaths from './pages/AttackPaths'
import ScanReport from './pages/ScanReport'
import SetupPage from './pages/SetupPage'
import Alerts from './pages/Alerts'
import { ProjectProvider, useProject } from './context/ProjectContext'
import { ThemeProvider, useTheme } from './context/ThemeContext'
import { ToastProvider } from './components/ToastProvider'
import { ViolationsProvider, useViolationsContext } from './context/ViolationsContext'

function Sidebar() {
  const location = useLocation()
  const { projects, selectedProject, setSelectedProject, loading: projectsLoading } = useProject()
  const { theme, toggleTheme } = useTheme()

  const { unreadCount } = useViolationsContext()

  const navItems = [
    { href: '/agents', label: 'Agents' },
    { href: '/sessions', label: 'Sessions' },
    { href: '/topology', label: 'Topology' },
    { href: '/alerts', label: 'Alerts', showUnread: true },
    { href: '/scan', label: 'Scan Report' },
    { href: '/risk', label: 'Risk Dashboard' },
    { href: '/attacks', label: 'Attack Paths' },
  ] as const

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <img
          src="/tracectrl-logo-dark.png"
          alt="TraceCtrl"
          className="sidebar-logo-img sidebar-logo-img--dark"
        />
        <img
          src="/tracectrl-logo-light.png"
          alt="TraceCtrl"
          className="sidebar-logo-img sidebar-logo-img--light"
        />
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
      {navItems.slice(3).map(item => {
        const isActive = location.pathname === item.href || location.pathname.startsWith(item.href + '/')
        const showBadge = 'showUnread' in item && item.showUnread && unreadCount > 0
        return (
          <Link
            key={item.href}
            to={item.href}
            className={`nav-link${isActive ? ' active' : ''}`}
          >
            <span className="nav-link-label">{item.label}</span>
            {showBadge && (
              <span
                className="nav-unread-dot"
                aria-label={`${unreadCount} unread alerts`}
                title={`${unreadCount} unread`}
              />
            )}
          </Link>
        )
      })}

      <div className="sidebar-footer">
        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === 'dark' ? '☀️' : '🌙'} {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
        </button>
        <p>TraceCtrl v0.1.0</p>
        <p>by CloudsineAI</p>
      </div>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
      <ProjectProvider>
        <ToastProvider>
        <ViolationsProvider>
        <div className="layout">
          <a href="#main-content" className="sr-only">Skip to main content</a>
          <Sidebar />
          <main id="main-content" className="main-content">
            <Routes>
              <Route path="/" element={<Navigate to="/agents" replace />} />
              <Route path="/topology" element={<TopologyGraph />} />
              <Route path="/sessions" element={<Sessions />} />
              <Route path="/sessions/:traceId" element={<TraceDetail />} />
              <Route path="/agents" element={<Agents />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/risk" element={<RiskDashboard />} />
              <Route path="/attacks" element={<AttackPaths />} />
              <Route path="/setup" element={<SetupPage />} />
              <Route path="/scan" element={<ScanReport />} />
            </Routes>
          </main>
        </div>
        </ViolationsProvider>
        </ToastProvider>
      </ProjectProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
