import { SelectedNode } from './ScanTopologyCanvas'
import Drawer, { DrawerClose } from './shared/Drawer'

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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="detail-field">
      <div className="detail-field-label">{label}</div>
      <div className="detail-field-value">{children}</div>
    </div>
  )
}

type BadgeTone = 'critical' | 'high' | 'medium' | 'low' | 'pass' | 'neutral'
function Badge({ text, tone }: { text: string; tone: BadgeTone }) {
  return <span className={`panel-badge panel-badge-${tone}`}>{text}</span>
}

function CredBadge({ status }: { status: string }) {
  if (status === 'env_var')   return <Badge text="ENV VAR" tone="low" />
  if (status === 'plaintext') return <Badge text="PLAINTEXT ⚠" tone="high" />
  return <Badge text="NOT SET" tone="neutral" />
}

function DmPolicyBadge({ policy }: { policy: string }) {
  if (policy === 'allowlist') return <Badge text="allowlist" tone="low" />
  if (policy === 'open')      return <Badge text="open ⚠" tone="critical" />
  if (policy === 'pairing')   return <Badge text="pairing" tone="medium" />
  return <span className="panel-muted">{policy || '—'}</span>
}

function StringList({ items }: { items: unknown }) {
  const arr = Array.isArray(items) ? items.filter(Boolean) : []
  if (!arr.length) return <span className="panel-muted">none</span>
  return (
    <div className="panel-chipgroup">
      {arr.map((v, i) => <span className="panel-chip" key={i}>{String(v)}</span>)}
    </div>
  )
}

function SoulExcerpt({ text }: { text: string }) {
  if (!text) return <span className="panel-muted">No SOUL.md found</span>
  return (
    <pre className="panel-soul">
      {text}{text.length >= 500 ? '…' : ''}
    </pre>
  )
}

function IngressContent({ p }: { p: Record<string, unknown> }) {
  return (
    <>
      <Field label="DM Policy"><DmPolicyBadge policy={String(p.dm_policy ?? '')} /></Field>
      <Field label="Group Policy">
        {p.group_policy ? <DmPolicyBadge policy={String(p.group_policy)} /> : <span className="panel-muted">—</span>}
      </Field>
      <Field label="Allow From"><StringList items={p.allow_from} /></Field>
      {p.streaming && <Field label="Streaming">{String(p.streaming)}</Field>}
      <Field label="Bot Token">
        {p.has_token
          ? <span className="panel-mono">{String(p.token_tail)}</span>
          : <span className="panel-muted">not configured</span>}
      </Field>
    </>
  )
}

function AgentContent({ p }: { p: Record<string, unknown> }) {
  return (
    <>
      {p.primary_model  && <Field label="Primary Model">{String(p.primary_model)}</Field>}
      {p.workspace      && <Field label="Workspace">{String(p.workspace)}</Field>}
      {p.max_concurrent !== '' && p.max_concurrent !== undefined &&
        <Field label="Max Concurrent">{String(p.max_concurrent)}</Field>}
      {p.compaction_mode && <Field label="Compaction">{String(p.compaction_mode)}</Field>}
      {p.heartbeat       && <Field label="Heartbeat">{String(p.heartbeat)}</Field>}
      <Field label="Soul.md"><SoulExcerpt text={String(p.soul_excerpt ?? '')} /></Field>
    </>
  )
}

function ToolContent({ p }: { p: Record<string, unknown> }) {
  const securityLevel = p.security_level ? String(p.security_level) : null
  return (
    <>
      <Field label="Risk">
        {p.wildcard   ? <Badge text="WILDCARD — all tools permitted" tone="critical" /> :
         p.dangerous  ? <Badge text="DANGEROUS — arbitrary execution" tone="critical" /> :
                        <Badge text="Standard" tone="low" />}
      </Field>
      {securityLevel && (
        <Field label="Security Level">
          {securityLevel === 'full'      ? <Badge text="FULL — no restrictions" tone="critical" /> :
           securityLevel === 'allowlist' ? <Badge text="ALLOWLIST" tone="medium" /> :
           securityLevel === 'deny'      ? <Badge text="DENY LIST" tone="low" /> :
                                            <span className="panel-mono">{securityLevel}</span>}
        </Field>
      )}
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
          <span className="panel-mono panel-mono-accent">{primary}</span>
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
          <span className="panel-mono">{String(p.api_key_tail)}</span>
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
          ? <Badge text="HIGH — data write/read access" tone="high" />
          : <Badge text="Unknown — review required" tone="neutral" />}
      </Field>
      {p.capability && <Field label="Capability">{String(p.capability)}</Field>}
      <Field label={credKey}><CredBadge status={String(p.credential_status ?? 'none')} /></Field>
      {p.credential_status === 'plaintext' && p.credential_tail && (
        <Field label="Key Tail"><span className="panel-mono">{String(p.credential_tail)}</span></Field>
      )}
    </>
  )
}

function ExtensionContent({ p }: { p: Record<string, unknown> }) {
  return (
    <Field label="Status">
      {p.enabled !== false
        ? <Badge text="Enabled" tone="low" />
        : <Badge text="Disabled" tone="neutral" />}
    </Field>
  )
}

function SchedulerContent({ p }: { p: Record<string, unknown> }) {
  const isHeartbeat = p.type === 'heartbeat'
  const jobs = Array.isArray(p.jobs) ? p.jobs as Record<string, unknown>[] : []
  return (
    <>
      <Field label="Type">
        <Badge text={isHeartbeat ? 'HEARTBEAT' : 'CRON'} tone={isHeartbeat ? 'high' : 'medium'} />
      </Field>

      {isHeartbeat && p.interval && <Field label="Interval">{String(p.interval)}</Field>}
      {isHeartbeat && p.target   && <Field label="Output Channel">{String(p.target)}</Field>}
      {isHeartbeat && p.to       && <Field label="Recipient">{String(p.to)}</Field>}

      {!isHeartbeat && jobs.length > 0 && (
        <Field label={`Jobs (${jobs.length})`}>
          <div className="panel-joblist">
            {jobs.map((job, i) => {
              const jobName = String(job.name || job.id || `Job ${i + 1}`)
              const expr = job.expr ? String(job.expr) : ''
              const tz = job.timezone ? String(job.timezone) : ''
              const desc = job.description ? String(job.description) : ''
              const actionType = job.action_type ? String(job.action_type) : ''
              const sessionTarget = job.session_target ? String(job.session_target) : ''
              const active = job.enabled !== false
              return (
                <div key={i} className="panel-job">
                  <div className="panel-job-head">
                    <span className="panel-job-name">{jobName}</span>
                    <span className={`panel-job-state${active ? ' is-on' : ''}`}>
                      {active ? 'on' : 'off'}
                    </span>
                  </div>
                  {expr && (
                    <div className="panel-job-expr">
                      {expr}{tz && <span className="panel-job-tz">{tz}</span>}
                    </div>
                  )}
                  {desc && <div className="panel-job-desc">{desc}</div>}
                  {actionType && (
                    <div className="panel-job-desc">
                      action: <span className="panel-job-action">{actionType}</span>
                      {sessionTarget && <> · session: <span className="panel-job-action">{sessionTarget}</span></>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Field>
      )}

      {!isHeartbeat && jobs.length === 0 && (
        <Field label="Jobs"><span className="panel-muted">No jobs defined in cron/jobs.json</span></Field>
      )}

      <Field label="Risk">
        <span className="panel-note">
          Autonomous execution — agent runs without user initiation. Ensure SOUL.md restricts tool access during scheduled runs.
        </span>
      </Field>
    </>
  )
}

function GenericContent({ p }: { p: Record<string, unknown> }) {
  const entries = Object.entries(p).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  if (!entries.length) return <p className="panel-muted">No additional properties.</p>
  return (
    <>
      {entries.map(([k, v]) => (
        <Field key={k} label={k.replace(/_/g, ' ')}>{String(v)}</Field>
      ))}
    </>
  )
}

function renderContent(node: SelectedNode) {
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

export default function ScanNodePanel({ node, onClose }: Props) {
  const dotColor = node ? (NODE_COLORS[node.nodeType] ?? 'var(--gray-500)') : 'var(--gray-500)'

  return (
    <Drawer
      open={node !== null}
      onClose={onClose}
      ariaLabel={node ? `${node.nodeType} ${node.label}` : ''}
      tone="neutral"
      widthPx={420}
    >
      {node && (
        <>
          <header className="drawer-header">
            <span
              className="panel-node-dot"
              style={{ background: dotColor }}
              aria-hidden="true"
            />
            <div className="panel-node-heading">
              <div className="panel-node-type">{NODE_TYPE_LABELS[node.nodeType] ?? node.nodeType}</div>
              <h3 className="panel-node-label">{node.label}</h3>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <DrawerClose onClose={onClose} />
            </div>
          </header>

          <div className="drawer-body">
            <div className="panel-node-id">{node.id}</div>
            {renderContent(node)}
          </div>
        </>
      )}
    </Drawer>
  )
}
