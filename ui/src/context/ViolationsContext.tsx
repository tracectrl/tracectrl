import { createContext, ReactNode, useContext } from 'react'
import { useViolationStream } from '../hooks/useViolationStream'
import type { Violation } from '../api/violations'

interface ViolationsCtx {
  violations: Violation[]
  unreadCount: number
  markAllRead: () => void
  connected: boolean
}

const Ctx = createContext<ViolationsCtx | null>(null)

export function ViolationsProvider({ children }: { children: ReactNode }) {
  const stream = useViolationStream()
  return <Ctx.Provider value={stream}>{children}</Ctx.Provider>
}

export function useViolationsContext(): ViolationsCtx {
  const v = useContext(Ctx)
  if (!v) throw new Error('useViolationsContext must be used within <ViolationsProvider>')
  return v
}
