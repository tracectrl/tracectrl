import { SelectedNode } from './ScanTopologyCanvas'

const NODE_COLORS: Record<string, string> = {
  INGRESS: '#38BDF8',
  AGENT: '#4A90D9',
  TOOL: '#22C55E',
  LLM_PROVIDER: '#A78BFA',
  SCHEDULER: '#FFBB00',
  EXTENSION: '#FB923C',
  SUBAGENT_SURFACE: '#F472B6',
  STORAGE: '#6B7280',
  EXTERNAL_SERVICE: '#6B7280',
  SKILL: '#EC4899',
}

const NODE_TYPE_LABELS: Record<string, string> = {
  INGRESS: 'Ingress Channel',
  AGENT: 'Agent',
  TOOL: 'Tool',
  LLM_PROVIDER: 'LLM Provider',
  SCHEDULER: 'Scheduler',
  EXTENSION: 'Extension',
  SUBAGENT_SURFACE: 'Subagent Surface',
  STORAGE: 'Storage',
  EXTERNAL_SERVICE: 'External Service',
  SKILL: 'Skill',
}

interface Props {
  node: SelectedNode | null
  onClose: () => void
}

// ── small helpers ──────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="detail-field">
      <div className="detail-field-label">{label}</div>
      <div className="detail-field-value">{children}</div>
    </div>
  )
}

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      background: color + '22',
      color,
      border: `1px solid ${color}55`,
    }}>
      {text}
    </span>
  )
}

function CredBadge({ status }: { status: string }) {
  if (status === 'env_var')   return <Badge text="ENV VAR" color="#22C55E" />
  if (status === 'plaintext') return <Badge text="PLAINTEXT ⚠" color="#FF6B35" />
  return <Badge text="NOT SET" color="#6B7280" />
}

function DmPolicyBadge({ policy }: { policy: string }) {
  if (policy === 'allowlist') return <Badge text="allowlist" color="#22C55E" />
  if (policy === 'open')      return <Badge text="open ⚠" color="#FF4D4D" />
  if (policy === 'pairing')   return <Badge text="pairing" color="#FFBB00" />
  return <span style={{ color: 'var(--gray-500)', fontStyle: 'italic' }}>{policy || '—'}</span>
}

function StringList({ items }: { items: unknown }) {
  const arr = Array.isArray(items) ? items.filter(Boolean) : []
  if (!arr.length) return <span style={{ color: 'var(--gray-600)', fontStyle: 'italic' }}>none</span>
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {arr.map((v, i) => (
        <span key={i} style={{ background: 'var(--gray-800)', padding: '2px 7px', borderRadius: 4, fontSize: 12 }}>
          {String(v)}
        </span>
      ))}
    </div>
  )
}

function SoulExcerpt({ text }: { text: string }) {
  if (!text) return <span style={{ color: 'var(--gray-600)', fontStyle: 'italic' }}>No SOUL.md found</span>
  return (
    <pre style={{
      fontSize: 11,
      lineHeight: 1.6,
      color: 'var(--gray-400)',
      background: 'var(--dark-surface)',
      border: '1px solid var(--dark-border)',
      borderRadius: 6,
      padding: '10px 12px',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      maxHeight: 200,
      overflowY: 'auto',
      margin: 0,
    }}>
      {text}{text.length >= 500 ? '…' : ''}
    </pre>
  )
}

// ── per-type content ───────────────────────────────────────────────────────

function IngressContent({ p }: { p: Record<string, unknown> }) {
  return (
    <>
      <Field label="DM Policy"><DmPolicyBadge policy={String(p.dm_policy ?? '')} /></Field>
      <Field label="Group Policy">
        {p.group_policy ? <DmPolicyBadge policy={String(p.group_policy)} /> : <span style={{ color: 'var(--gray-600)', fontStyle: 'italic' }}>—</span>}
      </Field>
      <Field label="Allow From"><StringList items={p.allow_from} /></Field>
      {p.streaming && <Field label="Streaming">{String(p.streaming)}</Field>}
      <Field label="Bot Token">
        {p.has_token
          ? <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--gray-400)' }}>{String(p.token_tail)}</span>
          : <span style={{ color: 'var(--gray-600)', fontStyle: 'italic' }}>not configured</span>}
      </Field>
    </>
  )
}

function AgentContent({ p }: { p: Record<string, unknown> }) {
  return (
    <>
      {p.primary_model && <Field label="Primary Model">{String(p.primary_model)}</Field>}
      {p.workspace     && <Field label="Workspace">{String(p.workspace)}</Field>}
      {p.max_concurrent !== '' && p.max_concurrent !== undefined &&
        <Field label="Max Concurrent">{String(p.max_concurrent)}</Field>}
      {p.compaction_mode && <Field label="Compaction">{String(p.compaction_mode)}</Field>}
      {p.heartbeat && <Field label="Heartbeat">{String(p.heartbeat)}</Field>}
      <Field label="Soul.md"><SoulExcerpt text={String(p.soul_excerpt ?? '')} /></Field>
    </>
  )
}

function ToolContent({ p }: { p: Record<string, unknown> }) {
  return (
    <>
      <Field label="Risk">
        {p.wildcard   ? <Badge text="WILDCARD — all tools permitted" color="#FF4D4D" /> :
         p.dangerous  ? <Badge text="DANGEROUS — arbitrary execution" color="#FF4D4D" /> :
                        <Badge text="Standard" color="#22C55E" />}
      </Field>
      {Array.isArray(p.allowed_domains) && (
        <Field label="Allowed Domains"><StringList items={p.allowed_domains} /></Field>
      )}
    </>
  )
}

function LlmContent({ p }: { p: Record<string, unknown> }) {
  const primary = String(p.primary_model ?? '')
  const allModels = Array.isArray(p.models) ? p.models as string[] : []
  const otherModels = allModels.filter(m => m !== primary)
  return (
    <>
      {primary && (
        <Field label="Active Model">
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 13,
            color: '#C87FFF', fontWeight: 600,
          }}>
            {primary}
          </span>
        </Field>
      )}
      {otherModels.length > 0 && (
        <Field label="Also Configured"><StringList items={otherModels} /></Field>
      )}
      {!primary && allModels.length > 0 && (
        <Field label="Models"><StringList items={allModels} /></Field>
      )}
      {p.base_url && <Field label="Base URL">{String(p.base_url)}</Field>}
      <Field label="API Key"><CredBadge status={String(p.api_key_status ?? 'none')} /></Field>
      {p.api_key_status === 'plaintext' && p.api_key_tail &&
        <Field label="Key Tail">
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--gray-400)' }}>{String(p.api_key_tail)}</span>
        </Field>}
    </>
  )
}

function SkillContent({ p }: { p: Record<string, unknown> }) {
  const credKey = p.credential_key ? String(p.credential_key) : 'API Key'
  return (
    <>
      <Field label="Risk Level">
        {p.risk_level === 'high'
          ? <Badge text="HIGH — data write/read access" color="#FF6B35" />
          : <Badge text="Unknown — review required" color="#6B7280" />}
      </Field>
      {p.capability && <Field label="Capability">{String(p.capability)}</Field>}
      <Field label={credKey}><CredBadge status={String(p.credential_status ?? 'none')} /></Field>
      {p.credential_status === 'plaintext' && p.credential_tail && (
        <Field label="Key Tail">
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--gray-400)' }}>
            {String(p.credential_tail)}
          </span>
        </Field>
      )}
    </>
  )
}

function ExtensionContent({ p }: { p: Record<string, unknown> }) {
  return (
    <Field label="Status">
      {p.enabled !== false
        ? <Badge text="Enabled" color="#22C55E" />
        : <Badge text="Disabled" color="#6B7280" />}
    </Field>
  )
}

function SchedulerContent({ p }: { p: Record<string, unknown> }) {
  const isHeartbeat = p.type === 'heartbeat'
  const jobs = Array.isArray(p.jobs) ? p.jobs as Record<string, unknown>[] : []
  return (
    <>
      <Field label="Type">
        <Badge
          text={isHeartbeat ? 'HEARTBEAT' : 'CRON'}
          color={isHeartbeat ? '#FB923C' : '#FFBB00'}
        />
      </Field>

      {/* Heartbeat fields */}
      {isHeartbeat && p.interval && <Field label="Interval">{String(p.interval)}</Field>}
      {isHeartbeat && p.target   && <Field label="Output Channel">{String(p.target)}</Field>}
      {isHeartbeat && p.to       && <Field label="Recipient">{String(p.to)}</Field>}

      {/* Cron jobs list */}
      {!isHeartbeat && jobs.length > 0 && (
        <Field label={`Jobs (${jobs.length})`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
            {jobs.map((job, i) => {
              const jobName = String(job.name || job.id || `Job ${i + 1}`)
              const expr = job.expr ? String(job.expr) : ''
              const tz = job.timezone ? String(job.timezone) : ''
              const desc = job.description ? String(job.description) : ''
              const actionType = job.action_type ? String(job.action_type) : ''
              const sessionTarget = job.session_target ? String(job.session_target) : ''
              const active = job.enabled !== false
              return (
                <div key={i} style={{
                  background: 'rgba(255,187,0,0.05)',
                  border: '1px solid rgba(255,187,0,0.15)',
                  borderRadius: 6,
                  padding: '8px 10px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--gray-200)' }}>{jobName}</span>
                    <span style={{ fontSize: 10, color: active ? '#22C55E' : '#6B7280', fontWeight: 600, textTransform: 'uppercase' }}>
                      {active ? 'on' : 'off'}
                    </span>
                  </div>
                  {expr && (
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#FFBB00', marginBottom: 2 }}>
                      {expr}
                      {tz && <span style={{ color: 'var(--gray-500)', marginLeft: 6 }}>{tz}</span>}
                    </div>
                  )}
                  {desc && (
                    <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 2 }}>{desc}</div>
                  )}
                  {actionType && (
                    <div style={{ fontSize: 11, color: 'var(--gray-500)', marginTop: 2 }}>
                      action: <span style={{ color: 'var(--gray-400)' }}>{actionType}</span>
                      {sessionTarget && <span style={{ marginLeft: 6 }}>· session: <span style={{ color: 'var(--gray-400)' }}>{sessionTarget}</span></span>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Field>
      )}

      {!isHeartbeat && jobs.length === 0 && (
        <Field label="Jobs">
          <span style={{ fontSize: 12, color: 'var(--gray-500)' }}>No jobs defined in cron/jobs.json</span>
        </Field>
      )}

      <Field label="Risk">
        <span style={{ fontSize: 12, color: 'var(--gray-400)', lineHeight: 1.5 }}>
          Autonomous execution — agent runs without user initiation.
          Ensure SOUL.md restricts tool access during scheduled runs.
        </span>
      </Field>
    </>
  )
}

function GenericContent({ p }: { p: Record<string, unknown> }) {
  const entries = Object.entries(p).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  if (!entries.length) return <p style={{ color: 'var(--gray-600)', fontSize: 13 }}>No additional properties.</p>
  return (
    <>
      {entries.map(([k, v]) => (
        <Field key={k} label={k.replace(/_/g, ' ')}>{String(v)}</Field>
      ))}
    </>
  )
}

// ── main panel ─────────────────────────────────────────────────────────────

export default function ScanNodePanel({ node, onClose }: Props) {
  const isOpen = node !== null

  const renderContent = () => {
    if (!node) return null
    const p = node.properties
    switch (node.nodeType) {
      case 'INGRESS':          return <IngressContent p={p} />
      case 'AGENT':            return <AgentContent p={p} />
      case 'TOOL':             return <ToolContent p={p} />
      case 'LLM_PROVIDER':     return <LlmContent p={p} />
      case 'SKILL':            return <SkillContent p={p} />
      case 'EXTENSION':        return <ExtensionContent p={p} />
      case 'SCHEDULER':        return <SchedulerContent p={p} />
      default:                 return <GenericContent p={p} />
    }
  }

  return (
    <div className={`detail-panel${isOpen ? ' open' : ''}`}>
      {node && (
        <>
          <div className="detail-panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                width: 10, height: 10, borderRadius: '50%',
                background: NODE_COLORS[node.nodeType] ?? '#6B7280',
                display: 'inline-block', flexShrink: 0,
              }} />
              <div>
                <div style={{ fontSize: 12, color: 'var(--gray-500)', marginBottom: 2 }}>
                  {NODE_TYPE_LABELS[node.nodeType] ?? node.nodeType}
                </div>
                <h3 style={{ margin: 0 }}>{node.label}</h3>
              </div>
            </div>
            <button className="detail-panel-close" onClick={onClose} aria-label="Close">✕</button>
          </div>

          <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--gray-700)', marginBottom: 'var(--space-5)' }}>
            {node.id}
          </div>

          {renderContent()}
        </>
      )}
    </div>
  )
}
