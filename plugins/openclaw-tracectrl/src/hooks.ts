/**
 * TraceCtrl OpenClaw hooks — uses onDiagnosticEvent (the same mechanism
 * as diagnostics-otel) plus api.on() typed hooks where available.
 *
 * The diagnostic event system is the ONLY reliable way to receive events
 * in external OpenClaw plugins. The api.on() typed hooks (message_received,
 * before_agent_start, tool_result_persist, agent_end) are not fully wired
 * for external plugins as of OpenClaw 2026.4.x.
 *
 * Trace hierarchy:
 *   tracectrl.request (root — created on message.processed event)
 *   ├── tracectrl.model.usage (child — created on model.usage event)
 *   └── tracectrl.model.usage (additional LLM calls in same session)
 */

import {
  context,
  SpanKind,
  SpanStatusCode,
  trace,
  type Context,
  type Span,
} from "@opentelemetry/api";
import type { TelemetryRuntime } from "./telemetry.js";
import type { TraceCtrlConfig } from "./config.js";
import { analyseMessageContent } from "./security.js";

// ---------------------------------------------------------------------------
// Session context tracking — links spans into parent-child traces
// ---------------------------------------------------------------------------

interface SessionTraceContext {
  rootSpan: Span;
  rootContext: Context;
  startTime: number;
  channel: string;
  sessionKey: string;
}

const sessionContextMap = new Map<string, SessionTraceContext>();

// ---------------------------------------------------------------------------
// Dynamic SDK loader — onDiagnosticEvent is only available at runtime
// ---------------------------------------------------------------------------

let onDiagnosticEvent: ((listener: (evt: any) => void) => () => void) | null =
  null;
let sdkLoaded = false;

async function loadSdk(logger: any): Promise<boolean> {
  if (sdkLoaded) return onDiagnosticEvent !== null;
  sdkLoaded = true;
  try {
    // @ts-ignore — openclaw SDK only available at runtime inside the gateway
    const sdk = await import("openclaw/plugin-sdk");
    if (typeof sdk.onDiagnosticEvent === "function") {
      onDiagnosticEvent = sdk.onDiagnosticEvent;
      logger.info("[tracectrl] Loaded onDiagnosticEvent from plugin-sdk");
      return true;
    }
    // Try alternate path
    // @ts-ignore — openclaw SDK only available at runtime inside the gateway
    const diag = await import("openclaw/plugin-sdk/diagnostic-runtime");
    if (typeof diag.onDiagnosticEvent === "function") {
      onDiagnosticEvent = diag.onDiagnosticEvent;
      logger.info(
        "[tracectrl] Loaded onDiagnosticEvent from diagnostic-runtime"
      );
      return true;
    }
  } catch {
    // Not available — fall back to api.registerHook only
  }
  logger.warn(
    "[tracectrl] onDiagnosticEvent not available — using registerHook fallback"
  );
  return false;
}

// ---------------------------------------------------------------------------
// Main registration
// ---------------------------------------------------------------------------

export function registerHooks(
  api: any,
  telemetry: TelemetryRuntime,
  config: TraceCtrlConfig
): void {
  const { tracer, counters, histograms } = telemetry;
  const logger = api.logger;

  // -------------------------------------------------------------------
  // Strategy 1: Diagnostic events (works reliably in all OpenClaw versions)
  // -------------------------------------------------------------------

  loadSdk(logger).then((hasDiagnostics) => {
    if (hasDiagnostics && onDiagnosticEvent) {
      registerDiagnosticListeners(
        tracer,
        counters,
        histograms,
        config,
        logger
      );
    }
  });

  // -------------------------------------------------------------------
  // Strategy 2: Event-stream hooks via api.registerHook (always available)
  // These fire for command lifecycle and gateway events
  // -------------------------------------------------------------------

  try {
    api.registerHook(
      ["command:new", "command:reset", "command:stop"],
      async (event: any) => {
        try {
          const action = event?.action ?? "unknown";
          const sessionKey = event?.sessionKey ?? "unknown";

          const span = tracer.startSpan(`tracectrl.session.${action}`, {
            kind: SpanKind.INTERNAL,
            attributes: {
              "tracectrl.session.action": action,
              "tracectrl.session.key": sessionKey,
              "tracectrl.command.source":
                event?.context?.commandSource ?? "unknown",
            },
          });

          if (action === "new" || action === "reset") {
            counters.sessionResets.add(1);
          }

          span.setStatus({ code: SpanStatusCode.OK });
          span.end();
        } catch {
          // Never let telemetry break the gateway
        }
      },
      { name: "tracectrl-session-events" }
    );
    logger.info("[tracectrl] Registered command event hooks");
  } catch (err) {
    logger.warn(
      `[tracectrl] Could not register command hooks: ${err instanceof Error ? err.message : String(err)}`
    );
  }

  try {
    api.registerHook(
      "gateway:startup",
      async () => {
        try {
          const span = tracer.startSpan("tracectrl.gateway.startup", {
            kind: SpanKind.INTERNAL,
          });
          span.setStatus({ code: SpanStatusCode.OK });
          span.end();
        } catch {
          // ignore
        }
      },
      { name: "tracectrl-gateway-startup" }
    );
    logger.info("[tracectrl] Registered gateway:startup hook");
  } catch (err) {
    logger.warn(
      `[tracectrl] Could not register gateway hook: ${err instanceof Error ? err.message : String(err)}`
    );
  }

  // -------------------------------------------------------------------
  // Strategy 3: api.on() typed hooks — may not fire in all versions
  // but register them anyway in case future OpenClaw versions wire them
  // -------------------------------------------------------------------

  try {
    api.on(
      "message_received",
      async (event: any) => {
        try {
          const channel = event?.channel ?? "unknown";
          const sessionKey =
            event?.sessionKey ?? event?.session_key ?? `anon-${Date.now()}`;

          const rootSpan = tracer.startSpan("tracectrl.request", {
            kind: SpanKind.SERVER,
            attributes: {
              "tracectrl.channel": channel,
              "tracectrl.session.key": sessionKey,
              "tracectrl.message.direction": "inbound",
              "tracectrl.message.from": event?.from ?? event?.senderId ?? "unknown",
            },
          });

          const rootContext = trace.setSpan(context.active(), rootSpan);
          sessionContextMap.set(sessionKey, {
            rootSpan,
            rootContext,
            startTime: Date.now(),
            channel,
            sessionKey,
          });

          counters.messagesReceived.add(1, {
            "tracectrl.channel": channel,
          });

          // Security: check for prompt injection
          const text = event?.text ?? event?.message ?? "";
          if (text && config.captureContent) {
            analyseMessageContent(text, rootSpan, telemetry);
          }
        } catch {
          // ignore
        }
        return undefined;
      },
      { priority: 100 }
    );
    logger.info("[tracectrl] Registered message_received hook (may not fire in all versions)");
  } catch {
    // api.on may not accept this event name — that's OK
  }

  try {
    api.on(
      "agent_end",
      async (event: any) => {
        try {
          const sessionKey =
            event?.sessionKey ?? event?.session_key ?? "unknown";
          const session = sessionContextMap.get(sessionKey);
          if (session) {
            session.rootSpan.setStatus({ code: SpanStatusCode.OK });
            session.rootSpan.end();
            sessionContextMap.delete(sessionKey);
          }
        } catch {
          // ignore
        }
        return undefined;
      },
      { priority: -100 }
    );
    logger.info("[tracectrl] Registered agent_end hook (may not fire in all versions)");
  } catch {
    // ignore
  }

  // -------------------------------------------------------------------
  // Periodic cleanup of stale session contexts (5 min TTL)
  // -------------------------------------------------------------------

  setInterval(() => {
    const now = Date.now();
    for (const [key, ctx] of sessionContextMap) {
      if (now - ctx.startTime > 5 * 60 * 1000) {
        try {
          ctx.rootSpan.end();
        } catch {
          // ignore
        }
        sessionContextMap.delete(key);
      }
    }
  }, 60_000);

  logger.info("[tracectrl] All hooks registered");
}

// ---------------------------------------------------------------------------
// Diagnostic event listeners — the reliable telemetry path
// ---------------------------------------------------------------------------

function registerDiagnosticListeners(
  tracer: any,
  counters: TelemetryRuntime["counters"],
  histograms: TelemetryRuntime["histograms"],
  config: TraceCtrlConfig,
  logger: any
): void {
  if (!onDiagnosticEvent) return;

  onDiagnosticEvent((evt: any) => {
    try {
      const type = evt?.type;

      // ── message.processed ──────────────────────────────────────
      if (type === "message.processed") {
        const sessionKey = evt.sessionKey ?? "unknown";
        const channel = evt.channel ?? "unknown";

        // Create or reuse root span for this session
        let session = sessionContextMap.get(sessionKey);
        if (!session) {
          const rootSpan = tracer.startSpan("tracectrl.request", {
            kind: SpanKind.SERVER,
            attributes: {
              "tracectrl.channel": channel,
              "tracectrl.session.key": sessionKey,
              "tracectrl.message.outcome": evt.outcome ?? "unknown",
              "tracectrl.message.id": evt.messageId ?? "",
            },
          });
          const rootContext = trace.setSpan(context.active(), rootSpan);
          session = {
            rootSpan,
            rootContext,
            startTime: Date.now(),
            channel,
            sessionKey,
          };
          sessionContextMap.set(sessionKey, session);
        } else {
          // Update existing root span with message outcome
          session.rootSpan.setAttribute(
            "tracectrl.message.outcome",
            evt.outcome ?? "unknown"
          );
        }

        counters.messagesReceived.add(1, {
          "tracectrl.channel": channel,
        });

        // End root span after a delay (message lifecycle complete)
        setTimeout(() => {
          const s = sessionContextMap.get(sessionKey);
          if (s && s === session) {
            s.rootSpan.setStatus({ code: SpanStatusCode.OK });
            s.rootSpan.end();
            sessionContextMap.delete(sessionKey);
          }
        }, 2000);
      }

      // ── model.usage ────────────────────────────────────────────
      if (type === "model.usage") {
        const sessionKey = evt.sessionKey ?? "unknown";
        const model = evt.model ?? "unknown";
        const provider = evt.provider ?? "unknown";
        const channel = evt.channel ?? "unknown";

        // Get parent context if available
        const session = sessionContextMap.get(sessionKey);
        const parentCtx = session?.rootContext ?? context.active();

        // Create child span for this LLM call
        const modelSpan = tracer.startSpan(
          "tracectrl.model.usage",
          {
            kind: SpanKind.INTERNAL,
            attributes: {
              "tracectrl.model": model,
              "tracectrl.provider": provider,
              "tracectrl.channel": channel,
              "tracectrl.session.key": sessionKey,
              "gen_ai.response.model": model,
              "gen_ai.system": provider,
            },
          },
          parentCtx
        );

        // Token usage
        const usage = evt.usage ?? {};
        const inputTokens = usage.input ?? usage.inputTokens ?? 0;
        const outputTokens = usage.output ?? usage.outputTokens ?? 0;
        const cacheRead = usage.cacheRead ?? 0;
        const cacheWrite = usage.cacheWrite ?? 0;
        const totalTokens = inputTokens + outputTokens + cacheRead + cacheWrite;

        modelSpan.setAttribute("gen_ai.usage.input_tokens", inputTokens);
        modelSpan.setAttribute("gen_ai.usage.output_tokens", outputTokens);
        modelSpan.setAttribute("gen_ai.usage.total_tokens", totalTokens);

        if (cacheRead > 0) {
          modelSpan.setAttribute("gen_ai.usage.cache_read_tokens", cacheRead);
        }
        if (cacheWrite > 0) {
          modelSpan.setAttribute("gen_ai.usage.cache_write_tokens", cacheWrite);
        }

        // Cost
        if (typeof evt.costUsd === "number") {
          modelSpan.setAttribute("tracectrl.cost_usd", evt.costUsd);
        }

        // Context window
        if (evt.context?.limit) {
          modelSpan.setAttribute("tracectrl.context.limit", evt.context.limit);
        }
        if (evt.context?.used) {
          modelSpan.setAttribute("tracectrl.context.used", evt.context.used);
        }

        // Duration
        if (typeof evt.durationMs === "number") {
          modelSpan.setAttribute("tracectrl.duration_ms", evt.durationMs);
          histograms.agentTurnDuration.record(evt.durationMs, {
            "tracectrl.model": model,
          });
        }

        // Metrics
        counters.tokensPrompt.add(inputTokens + cacheRead + cacheWrite, {
          "tracectrl.model": model,
        });
        counters.tokensCompletion.add(outputTokens, {
          "tracectrl.model": model,
        });
        counters.tokensTotal.add(totalTokens, {
          "tracectrl.model": model,
        });

        modelSpan.setStatus({ code: SpanStatusCode.OK });
        modelSpan.end();

        logger.info(
          `[tracectrl] model.usage: ${model} — ${inputTokens}in/${outputTokens}out tokens`
        );
      }

      // ── webhook.received ───────────────────────────────────────
      if (type === "webhook.received") {
        counters.messagesReceived.add(1, {
          "tracectrl.channel": evt.channel ?? "unknown",
        });
      }

      // ── webhook.error ──────────────────────────────────────────
      if (type === "webhook.error") {
        const span = tracer.startSpan("tracectrl.webhook.error", {
          kind: SpanKind.INTERNAL,
          attributes: {
            "tracectrl.channel": evt.channel ?? "unknown",
            "tracectrl.error": evt.error ?? "unknown",
          },
        });
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: String(evt.error ?? "webhook error"),
        });
        span.end();
      }

      // ── session.stuck ──────────────────────────────────────────
      if (type === "session.stuck") {
        const span = tracer.startSpan("tracectrl.session.stuck", {
          kind: SpanKind.INTERNAL,
          attributes: {
            "tracectrl.session.key": evt.sessionKey ?? "unknown",
            "tracectrl.session.state": evt.state ?? "unknown",
            "tracectrl.session.age_ms": evt.ageMs ?? 0,
          },
        });
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: "Session stuck",
        });
        span.end();
      }
    } catch (err) {
      // Never let telemetry errors affect the gateway
      logger.error?.(
        `[tracectrl] diagnostic event error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
  });

  logger.info("[tracectrl] Diagnostic event listener registered");
}
