export interface TraceCtrlConfig {
  endpoint: string;
  serviceName: string;
  captureContent: boolean;
  protocol: "http" | "grpc";
  traces: boolean;
  metrics: boolean;
  metricsIntervalMs: number;
  headers: Record<string, string>;
}

const DEFAULTS: TraceCtrlConfig = {
  endpoint: "http://localhost:4318",
  serviceName: "openclaw-gateway",
  captureContent: false,
  protocol: "http",
  traces: true,
  metrics: true,
  metricsIntervalMs: 30_000,
  headers: {},
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function parseConfig(raw: unknown): TraceCtrlConfig {
  if (!raw || !isRecord(raw)) {
    return { ...DEFAULTS };
  }

  const endpoint =
    typeof raw.endpoint === "string" && raw.endpoint.length > 0
      ? raw.endpoint
      : DEFAULTS.endpoint;

  const serviceName =
    typeof raw.serviceName === "string" && raw.serviceName.length > 0
      ? raw.serviceName
      : DEFAULTS.serviceName;

  const captureContent =
    typeof raw.captureContent === "boolean"
      ? raw.captureContent
      : DEFAULTS.captureContent;

  const protocol =
    raw.protocol === "grpc" ? ("grpc" as const) : DEFAULTS.protocol;

  const traces =
    typeof raw.traces === "boolean" ? raw.traces : DEFAULTS.traces;

  const metrics =
    typeof raw.metrics === "boolean" ? raw.metrics : DEFAULTS.metrics;

  const metricsIntervalMs =
    typeof raw.metricsIntervalMs === "number" && raw.metricsIntervalMs > 0
      ? raw.metricsIntervalMs
      : DEFAULTS.metricsIntervalMs;

  let headers: Record<string, string> = {};
  if (isRecord(raw.headers)) {
    for (const [k, v] of Object.entries(raw.headers)) {
      if (typeof v === "string") {
        headers[k] = v;
      }
    }
  }

  return {
    endpoint,
    serviceName,
    captureContent,
    protocol,
    traces,
    metrics,
    metricsIntervalMs,
    headers,
  };
}
