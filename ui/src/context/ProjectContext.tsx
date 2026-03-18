import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface ProjectContextType {
  projects: string[]
  selectedProject: string | null  // null = "All Projects"
  setSelectedProject: (project: string | null) => void
  loading: boolean
}

const ProjectContext = createContext<ProjectContextType>({
  projects: [],
  selectedProject: null,
  setSelectedProject: () => {},
  loading: true,
})

export function useProject() {
  return useContext(ProjectContext)
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<string[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'http://localhost:8000'
    fetch(`${ENGINE_URL}/api/v1/projects`)
      .then(res => res.json())
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <ProjectContext.Provider value={{ projects, selectedProject, setSelectedProject, loading }}>
      {children}
    </ProjectContext.Provider>
  )
}
