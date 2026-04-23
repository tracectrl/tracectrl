// Hand-crafted pointers for non-auto-fixable checks.
//
// Each entry names the problem, tells the agent *where* in the OpenClaw
// workspace to look, and points at the specific docs.openclaw.ai page
// that documents the relevant config. The agent then researches + applies
// the fix itself.
//
// Missing entries fall back to the scanner-supplied `remediation` string.

export interface AgentBrief {
  problem: string     // one-line plain-English description
  location: string    // file / JSON path or filesystem location to inspect
  docsUrl: string     // full docs.openclaw.ai URL (not anchor-less root)
  hint?: string       // optional one-liner nudge on the shape of the fix
}

const D = 'https://docs.openclaw.ai'

export const AGENT_BRIEFS: Record<string, AgentBrief> = {
  // ── Advanced Security ─────────────────────────────────────────
  'OC-SEC-001': {
    problem: 'Gateway is network-exposed but does not require authentication.',
    location: 'openclaw.json → gateway.bind, gateway.auth',
    docsUrl: `${D}/gateway/authentication`,
    hint: 'Either bind the gateway to loopback or require an auth token (env-var reference, never inline).',
  },
  'OC-SEC-002': {
    problem: 'One or more "dangerously*" override flags are enabled (23 known dangerous flags).',
    location: 'openclaw.json — search recursively for keys beginning with "dangerously"',
    docsUrl: `${D}/gateway/sandbox-vs-tool-policy-vs-elevated`,
    hint: 'Remove or explicitly justify each dangerous override; prefer tool-policy / sandbox controls instead.',
  },
  'OC-SEC-003': {
    problem: 'The exec tool is enabled without a tightened security level.',
    location: 'openclaw.json → tools.exec.security_level',
    docsUrl: `${D}/tools/exec`,
    hint: 'Set security_level to "allowlist" or "deny"; avoid "full" (no restrictions) in production.',
  },
  'OC-SEC-004': {
    problem: 'Agent sandbox mode is not enforced.',
    location: 'openclaw.json → agents.<name>.sandbox or top-level sandbox config',
    docsUrl: `${D}/gateway/sandboxing`,
    hint: 'Enable sandbox mode for every agent that calls tools; confirm the chosen sandbox backend is installed.',
  },
  'OC-SEC-005': {
    problem: 'Browser / web_fetch SSRF policy does not block private networks.',
    location: 'openclaw.json → tools.browser.ssrf_policy and tools.web_fetch.ssrf_policy',
    docsUrl: `${D}/tools/browser`,
    hint: 'Set an explicit SSRF policy that denies RFC1918, loopback, link-local and metadata service ranges.',
  },

  // ── Credentials ───────────────────────────────────────────────
  'OC-CRED-001': {
    problem: 'Plaintext secrets found under sensitive key names (apikey, token, password, secret, key).',
    location: 'openclaw.json and any referenced sub-configs (recursive scan)',
    docsUrl: `${D}/gateway/secrets`,
    hint: 'Replace inline values with ${ENV_VAR} references and move real values to the operator\'s .env.',
  },
  'OC-CRED-002': {
    problem: '.env file is not listed in .gitignore — risk of committing secrets.',
    location: '.gitignore at the workspace root',
    docsUrl: `${D}/gateway/secrets`,
    hint: 'Add ".env" (and ".env.*") to .gitignore and verify no prior commit exposed the file.',
  },

  // ── Tools Authorization ──────────────────────────────────────
  'OC-TOOL-003': {
    problem: 'web_fetch is enabled without a domain allowlist (SSRF / data-exfil risk).',
    location: 'openclaw.json → tools.web_fetch.allowed_domains',
    docsUrl: `${D}/tools/web-fetch`,
    hint: 'Populate allowed_domains with the exact hosts the agent needs; leave wildcards out.',
  },

  // ── Skills / Plugin Security ──────────────────────────────────
  'OC-SKILL-001': {
    problem: 'A skill credential is stored inline instead of as an env-var reference.',
    location: 'openclaw.json → skills.<name>.credentials and skills.*.apiKey / token',
    docsUrl: `${D}/tools/skills-config`,
    hint: 'Move every credential to ${ENV_VAR} form; real values belong only in .env.',
  },
  'OC-SKILL-002': {
    problem: 'A high data-risk skill is enabled (write-capable / DB / code-exec / cloud / payments).',
    location: 'openclaw.json → skills.<name>',
    docsUrl: `${D}/tools/skills`,
    hint: 'Confirm this skill is intentional; scope its credentials to read-only or a constrained workspace where possible.',
  },
  'OC-SKILL-003': {
    problem: 'More than 5 skills enabled — surface area is above the recommended ceiling.',
    location: 'openclaw.json → skills.*',
    docsUrl: `${D}/tools/skills`,
    hint: 'Disable or remove skills the agent does not actively use; prefer explicit enablement over bulk-include.',
  },
  'OC-SKILL-004': {
    problem: 'A skill has an unknown risk profile and requires manual review.',
    location: 'openclaw.json → skills.<name>',
    docsUrl: `${D}/tools/skills`,
    hint: 'Document whether this skill is read-only or write-capable and pin it to the appropriate risk tier in config.',
  },

  // ── Guardrails & Prompt Injection ─────────────────────────────
  'OC-GUARD-001': {
    problem: 'An agent has no SOUL.md (system prompt) — prompt-injection guardrails are missing.',
    location: 'agents/<agent-name>/SOUL.md (or the path configured in agents.<name>.soul)',
    docsUrl: `${D}/concepts/soul`,
    hint: 'Create a SOUL.md per agent; the template in /reference/templates/SOUL is a good starting point.',
  },
  'OC-GUARD-002': {
    problem: 'Content filter is not enabled for the agent.',
    location: 'openclaw.json → guardrails.content_filter.enabled (or per-agent override)',
    docsUrl: `${D}/gateway/security`,
    hint: 'Enable the content filter with a reasonable default policy; audit the allow/deny lists.',
  },

  // ── Network ───────────────────────────────────────────────────
  'OC-NET-002': {
    problem: 'Webhook endpoints accept plain HTTP instead of requiring TLS.',
    location: 'openclaw.json → webhooks.*.url or channels.webhook.*',
    docsUrl: `${D}/plugins/webhooks`,
    hint: 'Rewrite webhook URLs to https:// and reject http:// at the receiving side.',
  },
  'OC-NET-003': {
    problem: 'Gateway allowed_hosts list is not configured — any Host header is accepted.',
    location: 'openclaw.json → gateway.allowed_hosts',
    docsUrl: `${D}/gateway/configuration`,
    hint: 'Set allowed_hosts to the exact hostnames clients will use; reject everything else at the gateway.',
  },

  // ── Ingress / Channels ────────────────────────────────────────
  'OC-ING-002': {
    problem: 'A webhook ingress has no authentication token configured.',
    location: 'openclaw.json → channels.<name>.webhook.token (or equivalent per-channel key)',
    docsUrl: `${D}/plugins/webhooks`,
    hint: 'Generate a strong token, store it in env, reference it as ${...} in config, and verify on every inbound request.',
  },

  // ── Lateral Movement ──────────────────────────────────────────
  'OC-LAT-001': {
    problem: 'Sub-agent spawning is unrestricted — any agent can invoke any other.',
    location: 'openclaw.json → agents.<name>.subagents (allowAgents, maxSpawnDepth, requireAgentId)',
    docsUrl: `${D}/tools/subagents`,
    hint: 'Define allowAgents allowlists, cap maxSpawnDepth, and require explicit agent IDs instead of wildcards.',
  },

  // ── Filesystem ────────────────────────────────────────────────
  'OC-FS-001': {
    problem: 'openclaw.json is world-readable on disk.',
    location: 'filesystem permissions of openclaw.json',
    docsUrl: `${D}/gateway/secrets`,
    hint: 'chmod 600 (or 640 for group-read) on openclaw.json; verify the owner matches the gateway user.',
  },
  'OC-FS-002': {
    problem: 'Credentials directory has insecure permissions.',
    location: 'filesystem permissions of the credentials/secrets directory',
    docsUrl: `${D}/gateway/secrets`,
    hint: 'chmod 700 on the directory and 600 on every file inside; confirm ownership.',
  },

  // ── LLM Provider ──────────────────────────────────────────────
  'OC-LLM-001': {
    problem: 'LLM provider config is missing the provider field or uses a non-HTTPS endpoint.',
    location: 'openclaw.json → providers.<name>.provider and providers.<name>.base_url',
    docsUrl: `${D}/providers/index`,
    hint: 'Populate the provider field and ensure base_url is https:// — reject http:// for any remote endpoint.',
  },

  // ── Audit Logging ─────────────────────────────────────────────
  'OC-LOG-001': {
    problem: 'Audit logging is not enabled.',
    location: 'openclaw.json → logging.audit.enabled',
    docsUrl: `${D}/gateway/logging`,
    hint: 'Enable audit logging with a retention policy that matches your compliance target.',
  },

  // ── Compliance & Data Governance ──────────────────────────────
  'OC-COMP-001': {
    problem: 'Session data retention policy is missing (no pruneAfter / maxEntries).',
    location: 'openclaw.json → sessions.pruning or concepts.session.retention',
    docsUrl: `${D}/concepts/session-pruning`,
    hint: 'Configure pruneAfter (time-based) and/or maxEntries (count-based) explicitly; never leave retention unbounded.',
  },
  'OC-COMP-002': {
    problem: 'Session scope is not isolated per user (dmScope not set).',
    location: 'openclaw.json → sessions.dmScope or channels.<name>.dmScope',
    docsUrl: `${D}/concepts/session`,
    hint: 'Set dmScope to "user" so one user\'s conversation state cannot leak into another\'s.',
  },
  'OC-COMP-003': {
    problem: 'Sensitive-data redaction is not configured in the logging pipeline.',
    location: 'openclaw.json → logging.redaction or logging.filters',
    docsUrl: `${D}/gateway/logging`,
    hint: 'Enable redaction for PII / secrets / tokens; add custom patterns for domain-specific sensitive fields.',
  },

  // ── Persistence & Scheduling ──────────────────────────────────
  'OC-PERS-002': {
    problem: 'Session maintenance (compaction / pruning) is not configured.',
    location: 'openclaw.json → sessions.compaction and sessions.pruning',
    docsUrl: `${D}/reference/session-management-compaction`,
    hint: 'Enable compaction at a sensible interval and pair with pruning; without this, sessions grow unbounded.',
  },
  'OC-PERS-003': {
    problem: 'Heartbeat scheduler is enabled but not acknowledged as intentional.',
    location: 'openclaw.json → heartbeat or scheduler.heartbeat',
    docsUrl: `${D}/reference/templates/HEARTBEAT`,
    hint: 'If heartbeat is intentional, mark it acknowledged in config; otherwise disable it.',
  },

  // ── Operational Health ────────────────────────────────────────
  'OC-OPS-001': {
    problem: 'Primary LLM model is not configured for this agent.',
    location: 'openclaw.json → agents.<name>.model or providers.default',
    docsUrl: `${D}/providers/models`,
    hint: 'Pick a primary model matched to the agent\'s task (reasoning vs fast vs vision) and pin it.',
  },
  'OC-OPS-002': {
    problem: 'Fallback LLM model is not configured — a single provider outage kills the agent.',
    location: 'openclaw.json → agents.<name>.fallback_model or model_failover config',
    docsUrl: `${D}/concepts/model-failover`,
    hint: 'Configure a fallback on a different provider; verify the fallback actually engages during a simulated outage.',
  },

  // ── Plugin Integrity ──────────────────────────────────────────
  'OC-PLUG-001': {
    problem: 'A plugin is installed without an openclaw.plugin.json manifest.',
    location: 'plugins/<plugin-name>/openclaw.plugin.json',
    docsUrl: `${D}/plugins/manifest`,
    hint: 'Add a manifest declaring id, version, entrypoints and required permissions; reject unmanifested plugins.',
  },

  // ── Compound Risk ─────────────────────────────────────────────
  'COMPOUND-001': {
    problem: '"Prompt Injection Highway" — internet ingress + web_fetch + no SOUL.md on the receiving agent.',
    location: 'openclaw.json → channels.*, tools.web_fetch, agents.<name>.soul',
    docsUrl: `${D}/security/THREAT-MODEL-ATLAS`,
    hint: 'Break any one of the three legs: add SOUL.md guardrails, constrain web_fetch to an allowlist, or front the ingress with auth.',
  },
  'COMPOUND-002': {
    problem: 'Compound risk rule triggered — multiple vulnerabilities co-occur on this path.',
    location: 'openclaw.json — review the finding\'s path_nodes for the involved agents/tools',
    docsUrl: `${D}/security/THREAT-MODEL-ATLAS`,
    hint: 'Address the highest-severity leg first; often a single guardrail break the whole compound.',
  },
  'COMPOUND-003': {
    problem: 'Compound risk rule triggered — multiple vulnerabilities co-occur on this path.',
    location: 'openclaw.json — review the finding\'s path_nodes for the involved agents/tools',
    docsUrl: `${D}/security/THREAT-MODEL-ATLAS`,
    hint: 'Address the highest-severity leg first; often a single guardrail break the whole compound.',
  },
  'COMPOUND-004': {
    problem: 'Compound risk rule triggered — multiple vulnerabilities co-occur on this path.',
    location: 'openclaw.json — review the finding\'s path_nodes for the involved agents/tools',
    docsUrl: `${D}/security/THREAT-MODEL-ATLAS`,
    hint: 'Address the highest-severity leg first; often a single guardrail break the whole compound.',
  },
  'COMPOUND-005': {
    problem: 'Compound risk rule triggered — multiple vulnerabilities co-occur on this path.',
    location: 'openclaw.json — review the finding\'s path_nodes for the involved agents/tools',
    docsUrl: `${D}/security/THREAT-MODEL-ATLAS`,
    hint: 'Address the highest-severity leg first; often a single guardrail break the whole compound.',
  },
}
