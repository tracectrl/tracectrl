import { useCallback, useEffect, useState } from 'react'
import {
  PROTECTOR_GUARDRAILS,
  ProtectorConfig,
  ProtectorTestResult,
  fetchProtectorConfig,
  saveProtectorConfig,
  testProtectorConnection,
} from '../api/settings'
import ErrorBanner from '../components/shared/ErrorBanner'
import { useToast } from '../components/ToastProvider'

const PLACEHOLDER_ENDPOINT = 'https://genaifw-sales-demo.waftest.weborion.net'

export default function Settings() {
  const toast = useToast()

  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [endpointUrl, setEndpointUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  // Track whether the apiKey field is the redacted placeholder (from GET) or
  // a real value the user just typed. If the user saves without editing the
  // field, we keep the existing key on the server (PUT requires a full key
  // so we'd need to fetch the SDK endpoint, but that exposes the full key —
  // safer to require the user to re-enter on each save).
  const [apiKeyIsRedacted, setApiKeyIsRedacted] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [enabledKeys, setEnabledKeys] = useState<Set<string>>(new Set())
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<ProtectorTestResult | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    document.title = 'Settings — TraceCtrl'
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    fetchProtectorConfig()
      .then((cfg) => {
        setEndpointUrl(cfg.endpoint_url || '')
        setApiKey(cfg.api_key || '')
        setApiKeyIsRedacted(!!cfg.api_key)
        setEnabledKeys(new Set(cfg.enabled_guardrails || []))
        setUpdatedAt(cfg.updated_at || null)
        setLoadError(null)
      })
      .catch((err) => {
        setLoadError(err.message || 'Failed to load settings')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const onApiKeyChange = (next: string) => {
    setApiKey(next)
    setApiKeyIsRedacted(false)
  }

  const toggleGuardrail = (key: string) => {
    setEnabledKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const onSave = async () => {
    if (!endpointUrl.trim()) {
      toast.push({ severity: 'high', title: 'Endpoint URL is required' })
      return
    }
    if (apiKeyIsRedacted) {
      toast.push({
        severity: 'high',
        title: 'Re-enter your API key',
        body: 'The field shows a redacted placeholder — type the full key to save.',
      })
      return
    }
    if (!apiKey.trim()) {
      toast.push({ severity: 'high', title: 'API key is required' })
      return
    }

    setSaving(true)
    try {
      const cfg: ProtectorConfig = {
        endpoint_url: endpointUrl.trim().replace(/\/$/, ''),
        api_key: apiKey.trim(),
        enabled_guardrails: Array.from(enabledKeys),
      }
      const written = await saveProtectorConfig(cfg)
      setEndpointUrl(written.endpoint_url)
      setApiKey(written.api_key) // redacted form
      setApiKeyIsRedacted(true)
      setEnabledKeys(new Set(written.enabled_guardrails))
      setUpdatedAt(written.updated_at || null)
      toast.push({ severity: 'low', title: 'Settings saved' })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.push({ severity: 'high', title: 'Failed to save', body: msg })
    } finally {
      setSaving(false)
    }
  }

  const onTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testProtectorConnection()
      setTestResult(result)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setTestResult({ ok: false, ms: 0, error: msg })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="settings-page">
        <div className="page-header">
          <div className="section-tag">Configure</div>
          <h2>Settings</h2>
        </div>
        <div className="loading-skeleton" style={{ height: 280 }} />
      </div>
    )
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <div className="section-tag">Configure</div>
        <h2>TraceCtrl Guards</h2>
        <p className="page-meta">
          External LLM firewall (Protector Plus). Catches prompt injection, PII,
          content moderation, and system-prompt leakage.
        </p>
      </div>

      {loadError && <ErrorBanner error={loadError} onRetry={load} />}

      {updatedAt && (
        <div className="settings-saved-line text-muted">
          Last saved {new Date(updatedAt).toLocaleString()}
        </div>
      )}

      <div className="settings-field">
        <label className="setup-label" htmlFor="settings-endpoint">
          Endpoint URL
        </label>
        <p className="setup-hint">
          Base URL of your Protector Plus deployment, no trailing slash.
        </p>
        <input
          id="settings-endpoint"
          className="setup-input"
          type="url"
          placeholder={PLACEHOLDER_ENDPOINT}
          value={endpointUrl}
          onChange={(e) => setEndpointUrl(e.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      <div className="settings-field">
        <label className="setup-label" htmlFor="settings-apikey">
          API Key
        </label>
        <p className="setup-hint">
          Domain-scoped key from the Protector Plus dashboard. Stored once and
          never echoed back. The field shows a redacted placeholder after save.
        </p>
        <div className="settings-key-row">
          <input
            id="settings-apikey"
            className="setup-input"
            type={showKey ? 'text' : 'password'}
            placeholder="hOjm..."
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            className="btn btn-secondary settings-key-btn"
            onClick={() => setShowKey((s) => !s)}
          >
            {showKey ? 'Hide' : 'Show'}
          </button>
        </div>
        {apiKeyIsRedacted && (
          <p className="settings-key-redacted-note">
            Saved key is redacted. Re-enter the full key to save changes.
          </p>
        )}
      </div>

      <div className="settings-field">
        <span className="setup-label">Enabled guardrails</span>
        <p className="setup-hint">
          Each enabled guardrail is registered with TraceCtrl and runs on every
          <code> check_input</code> / <code>check_output</code> call from the SDK.
        </p>
        <div className="settings-guardrails-list">
          {PROTECTOR_GUARDRAILS.map((g) => {
            const isOn = enabledKeys.has(g.key)
            return (
              <button
                key={g.key}
                type="button"
                className={`settings-guardrail-toggle${isOn ? ' is-on' : ''}`}
                onClick={() => toggleGuardrail(g.key)}
                aria-pressed={isOn}
              >
                <span className="settings-guardrail-check" aria-hidden="true">
                  {isOn ? '✓' : ''}
                </span>
                <span className="settings-guardrail-text">
                  <span className="settings-guardrail-label">{g.label}</span>
                  <span className="settings-guardrail-desc">{g.description}</span>
                </span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="settings-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onTest}
          disabled={testing || !endpointUrl.trim()}
        >
          {testing ? 'Testing…' : 'Test Connection'}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {testResult && (
          <span
            className={`settings-test-result${testResult.ok ? ' is-ok' : ' is-err'}`}
            role="status"
          >
            {testResult.ok
              ? `✓ Healthy · ${testResult.ms}ms`
              : `✗ ${testResult.error || `HTTP ${testResult.status_code}`} · ${testResult.ms}ms`}
          </span>
        )}
      </div>
    </div>
  )
}
