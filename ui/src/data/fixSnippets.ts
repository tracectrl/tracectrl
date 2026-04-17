// Config snippets showing the target (fixed) state for each auto-fixable check.
// Used by ConfigCodeBlock to show operators what will change.
export const fixSnippets: Record<string, string> = {
  'OC-NET-001': `"gateway": {
  "bind": "loopback"
}`,
  'OC-ING-001': `"channels": {
  "<channel-name>": {
    "dmPolicy": "pairing"
  }
}`,
  'OC-TOOL-001': `// Remove "bash" and "exec" from tools.allow:
"tools": {
  "allow": ["<your-other-tools>"]
}`,
  'OC-TOOL-002': `// Remove wildcard from tools.allow:
"tools": {
  "allow": ["<explicit-tool-names>"]
}`,
  'OC-PERS-001': `"cron": {
  "enabled": false
}`,
  'OC-LOG-002': `"logging": {
  "level": "info"
}`,
}

export const AUTO_FIXABLE_IDS = new Set(Object.keys(fixSnippets))
