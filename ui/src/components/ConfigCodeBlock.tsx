import { useState } from 'react'
import { fixSnippets } from '../data/fixSnippets'

interface Props {
  checkId: string
}

export default function ConfigCodeBlock({ checkId }: Props) {
  const [copied, setCopied] = useState(false)
  const snippet = fixSnippets[checkId]
  if (!snippet) return null

  const handleCopy = () => {
    navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="config-code-block">
      <div className="config-code-header">
        <span className="config-code-label">Target config</span>
        <button className="btn btn-ghost btn-sm" onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="config-code-pre"><code>{snippet}</code></pre>
    </div>
  )
}
