import { type Span, SpanStatusCode } from "@opentelemetry/api";
import type { TelemetryRuntime } from "./telemetry.js";

// ---------------------------------------------------------------------------
// Dangerous tool names
// ---------------------------------------------------------------------------
const DANGEROUS_TOOLS = new Set([
  "bash",
  "shell",
  "exec",
  "execute",
  "run_command",
  "terminal",
  "subprocess",
]);

// ---------------------------------------------------------------------------
// Sensitive file patterns
// ---------------------------------------------------------------------------
const SENSITIVE_FILE_PATTERNS = [
  /\/etc\/passwd/,
  /\/etc\/shadow/,
  /\.env($|\.)/,
  /private[_-]?key/i,
  /id_rsa/,
  /id_ed25519/,
  /credentials\.json/i,
  /\.pem$/,
  /\.key$/,
  /aws_credentials/i,
  /\.kube\/config/,
  /token\.json/i,
  /secrets?\.(ya?ml|json|toml)/i,
];

// ---------------------------------------------------------------------------
// Prompt injection patterns
// ---------------------------------------------------------------------------
const INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?previous\s+instructions/i,
  /ignore\s+(all\s+)?prior\s+instructions/i,
  /disregard\s+(all\s+)?previous/i,
  /system\s+prompt\s+override/i,
  /you\s+are\s+now\s+(a|an)\s+/i,
  /new\s+instructions?\s*:/i,
  /forget\s+(all\s+)?your\s+(rules|instructions)/i,
  /pretend\s+you\s+are/i,
  /act\s+as\s+if\s+you\s+have\s+no\s+restrictions/i,
  /bypass\s+(your\s+)?(safety|content)\s+(filter|policy)/i,
  /do\s+not\s+follow\s+your\s+(rules|guidelines)/i,
  /jailbreak/i,
  /DAN\s+mode/i,
];

// ---------------------------------------------------------------------------
// Dangerous command patterns within tool inputs
// ---------------------------------------------------------------------------
const DANGEROUS_COMMAND_PATTERNS = [
  /\brm\s+-rf?\s/,
  /\bsudo\s/,
  /\bchmod\s+777\b/,
  /\bcurl\s+.*\|\s*(bash|sh)\b/,
  /\bwget\s+.*\|\s*(bash|sh)\b/,
  /\beval\s*\(/,
  /\b(nc|netcat|ncat)\s+-l/,
  /\breverse\s*shell/i,
  /\bbase64\s+-d\b.*\|\s*(bash|sh)/,
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface SecurityFinding {
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  description: string;
  detail?: string;
}

// ---------------------------------------------------------------------------
// Tool-level security checks
// ---------------------------------------------------------------------------

/**
 * Analyses a tool call for security-relevant signals. Returns an array of
 * findings (may be empty). Every finding is also written onto the span as
 * attributes and the security events counter is incremented.
 */
export function analyseToolCall(
  toolName: string,
  toolInput: string | undefined,
  span: Span,
  telemetry: TelemetryRuntime
): SecurityFinding[] {
  const findings: SecurityFinding[] = [];

  // 1. Dangerous tool name
  if (DANGEROUS_TOOLS.has(toolName.toLowerCase())) {
    findings.push({
      severity: "high",
      category: "dangerous_tool",
      description: `Invocation of dangerous tool: ${toolName}`,
    });
  }

  // 2. Dangerous commands inside input
  if (toolInput) {
    for (const pattern of DANGEROUS_COMMAND_PATTERNS) {
      const match = toolInput.match(pattern);
      if (match) {
        findings.push({
          severity: "high",
          category: "dangerous_command",
          description: `Dangerous command pattern detected: ${match[0]}`,
          detail: toolInput.slice(0, 500),
        });
        break; // one finding per category is enough
      }
    }
  }

  // 3. Sensitive file access
  if (toolInput) {
    for (const pattern of SENSITIVE_FILE_PATTERNS) {
      if (pattern.test(toolInput)) {
        findings.push({
          severity: "medium",
          category: "sensitive_file_access",
          description: `Sensitive file access detected: ${pattern.source}`,
          detail: toolInput.slice(0, 500),
        });
        break;
      }
    }
  }

  // Write findings onto the span
  if (findings.length > 0) {
    span.setAttribute("tracectrl.security.flagged", true);
    span.setAttribute("tracectrl.security.finding_count", findings.length);

    const maxSeverity = findings.reduce(
      (worst, f) => {
        const order: Record<string, number> = {
          low: 0,
          medium: 1,
          high: 2,
          critical: 3,
        };
        return (order[f.severity] ?? 0) > (order[worst] ?? 0)
          ? f.severity
          : worst;
      },
      "low" as string
    );
    span.setAttribute("tracectrl.security.max_severity", maxSeverity);

    // Serialize findings as a JSON attribute for downstream consumers
    span.setAttribute(
      "tracectrl.security.findings",
      JSON.stringify(
        findings.map((f) => ({
          severity: f.severity,
          category: f.category,
          description: f.description,
        }))
      )
    );

    telemetry.counters.securityEvents.add(findings.length, {
      "tracectrl.security.max_severity": maxSeverity,
    });
  }

  return findings;
}

// ---------------------------------------------------------------------------
// Content-level security checks (for message text)
// ---------------------------------------------------------------------------

/**
 * Scans message text for prompt-injection patterns. Returns findings and
 * annotates the span.
 */
export function analyseMessageContent(
  text: string,
  span: Span,
  telemetry: TelemetryRuntime
): SecurityFinding[] {
  const findings: SecurityFinding[] = [];

  for (const pattern of INJECTION_PATTERNS) {
    const match = text.match(pattern);
    if (match) {
      findings.push({
        severity: "critical",
        category: "prompt_injection",
        description: `Possible prompt injection detected: "${match[0]}"`,
        detail: text.slice(0, 500),
      });
      break; // one finding is sufficient to flag
    }
  }

  if (findings.length > 0) {
    span.setAttribute("tracectrl.security.flagged", true);
    span.setAttribute("tracectrl.security.finding_count", findings.length);
    span.setAttribute(
      "tracectrl.security.max_severity",
      findings[0].severity
    );
    span.setAttribute(
      "tracectrl.security.findings",
      JSON.stringify(
        findings.map((f) => ({
          severity: f.severity,
          category: f.category,
          description: f.description,
        }))
      )
    );

    telemetry.counters.securityEvents.add(findings.length, {
      "tracectrl.security.max_severity": findings[0].severity,
    });
  }

  return findings;
}
