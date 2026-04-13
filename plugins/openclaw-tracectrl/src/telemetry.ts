import {
  trace,
  metrics,
  type Tracer,
  type Meter,
  type Counter,
  type Histogram,
} from "@opentelemetry/api";
import {
  NodeTracerProvider,
  BatchSpanProcessor,
} from "@opentelemetry/sdk-trace-node";
import {
  MeterProvider,
  PeriodicExportingMetricReader,
} from "@opentelemetry/sdk-metrics";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { Resource } from "@opentelemetry/resources";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";
import type { TraceCtrlConfig } from "./config.js";

export interface TelemetryCounters {
  messagesReceived: Counter;
  messagesSent: Counter;
  toolCalls: Counter;
  toolErrors: Counter;
  tokensTotal: Counter;
  tokensPrompt: Counter;
  tokensCompletion: Counter;
  securityEvents: Counter;
  sessionResets: Counter;
}

export interface TelemetryHistograms {
  agentTurnDuration: Histogram;
  toolDuration: Histogram;
}

export interface TelemetryRuntime {
  tracer: Tracer;
  meter: Meter;
  counters: TelemetryCounters;
  histograms: TelemetryHistograms;
  shutdown: () => Promise<void>;
}

interface Logger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

export function initTelemetry(
  config: TraceCtrlConfig,
  logger: Logger
): TelemetryRuntime {
  const resource = new Resource({
    [ATTR_SERVICE_NAME]: config.serviceName,
    "tracectrl.plugin.version": "0.1.0",
  });

  // --- Traces ---
  let tracerProvider: NodeTracerProvider | undefined;

  if (config.traces) {
    const traceExporter = new OTLPTraceExporter({
      url: `${config.endpoint}/v1/traces`,
      headers: config.headers,
    });

    tracerProvider = new NodeTracerProvider({ resource });
    tracerProvider.addSpanProcessor(new BatchSpanProcessor(traceExporter));
    tracerProvider.register();

    logger.info("[tracectrl] Trace provider registered");
  }

  // --- Metrics ---
  let meterProvider: MeterProvider | undefined;

  if (config.metrics) {
    const metricExporter = new OTLPMetricExporter({
      url: `${config.endpoint}/v1/metrics`,
      headers: config.headers,
    });

    const metricReader = new PeriodicExportingMetricReader({
      exporter: metricExporter,
      exportIntervalMillis: config.metricsIntervalMs,
    });

    meterProvider = new MeterProvider({
      resource,
      readers: [metricReader],
    });
    metrics.setGlobalMeterProvider(meterProvider);

    logger.info("[tracectrl] Metric provider registered");
  }

  const tracer = trace.getTracer("tracectrl", "0.1.0");
  const meter = metrics.getMeter("tracectrl", "0.1.0");

  // --- Counters ---
  const counters: TelemetryCounters = {
    messagesReceived: meter.createCounter("tracectrl.messages.received", {
      description: "Number of inbound messages received",
    }),
    messagesSent: meter.createCounter("tracectrl.messages.sent", {
      description: "Number of outbound messages sent",
    }),
    toolCalls: meter.createCounter("tracectrl.tool.calls", {
      description: "Number of tool invocations",
    }),
    toolErrors: meter.createCounter("tracectrl.tool.errors", {
      description: "Number of tool invocations that returned errors",
    }),
    tokensTotal: meter.createCounter("tracectrl.tokens.total", {
      description: "Total tokens consumed",
    }),
    tokensPrompt: meter.createCounter("tracectrl.tokens.prompt", {
      description: "Prompt (input) tokens consumed",
    }),
    tokensCompletion: meter.createCounter("tracectrl.tokens.completion", {
      description: "Completion (output) tokens consumed",
    }),
    securityEvents: meter.createCounter("tracectrl.security.events", {
      description: "Security-relevant events detected",
    }),
    sessionResets: meter.createCounter("tracectrl.session.resets", {
      description: "Session reset events",
    }),
  };

  // --- Histograms ---
  const histograms: TelemetryHistograms = {
    agentTurnDuration: meter.createHistogram(
      "tracectrl.agent.turn.duration_ms",
      {
        description: "Duration of an agent turn in milliseconds",
        unit: "ms",
      }
    ),
    toolDuration: meter.createHistogram("tracectrl.tool.duration_ms", {
      description: "Duration of a tool call in milliseconds",
      unit: "ms",
    }),
  };

  // --- Shutdown ---
  async function shutdown(): Promise<void> {
    logger.info("[tracectrl] Shutting down telemetry providers");
    try {
      if (tracerProvider) {
        await tracerProvider.shutdown();
      }
      if (meterProvider) {
        await meterProvider.shutdown();
      }
    } catch (err) {
      logger.error(
        `[tracectrl] Error during telemetry shutdown: ${err instanceof Error ? err.message : String(err)}`
      );
    }
  }

  return { tracer, meter, counters, histograms, shutdown };
}
