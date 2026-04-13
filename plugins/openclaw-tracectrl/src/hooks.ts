/**
 * TraceCtrl OpenClaw hooks — session lifecycle, gateway events, and diagnostic
 * event telemetry for external OpenClaw plugins.
 *
 * The diagnostic event system (onDiagnosticEvent) is the most reliable way to
 * receive model-usage and message-processed events. However, it is an internal
 * module that is only directly importable from within the bundled extensions
 * directory (via a chunked relative path). External plugins installed to
 * ~/.openclaw/extensions/ cannot use that relative import.
 *
 * This module uses a multi-strategy approach:
 *   1. Try well-known npm package names (future SDK versions may expose it).
 *   2. Dynamically locate the OpenClaw install dir and import the stock
 *      diagnostics-otel api.js which re-exports onDiagnosticEvent.
 *   3. Fall back to hook-only mode — session lifecycle + gateway events still
 *      produce useful spans. The built-in diagnostics-otel plugin handles
 *      model.usage / message.processed spans and exports to the same collector.
 *
 * Trace hierarchy:
 *   tracectrl.request (root — created on message.processed event)
 *   +-- tracectrl.model.usage (child — created on model.usage event)
 *   +-- tracectrl.model.usage (additional LLM calls in same session)
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
import { execSync } from "node:child_process";
import { realpathSync, existsSync, readdirSync } from "node:fs";
import { resolve, dirname, join } from "node:path";

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

/**
 * Attempts to locate the OpenClaw installation directory by resolving the
 * `openclaw` binary through the PATH. Returns null if it cannot be found.
 */
function findOpenClawInstallDir(logger: any): string | null {
  try {
    // `which openclaw` gives us the bin path; resolve symlinks to get the real location
    const binPath = execSync("which openclaw", { encoding: "utf-8" }).trim();
    if (!binPath) return null;

    const realBin = realpathSync(binPath);
    // Typical nvm layout: .../node/v24.x/bin/openclaw -> .../node/v24.x/lib/node_modules/openclaw/...
    // Walk up from the bin to find the lib/node_modules/openclaw directory
    let dir = dirname(realBin);

    // Case 1: bin is a direct symlink into the package (e.g. dist/cli.js)
    // Walk up until we find a package.json with name "openclaw"
    for (let i = 0; i < 10; i++) {
      const pkgPath = join(dir, "package.json");
      if (existsSync(pkgPath)) {
        try {
          // @ts-ignore — dynamic require of JSON
          const pkg = JSON.parse(
            require("node:fs").readFileSync(pkgPath, "utf-8")
          );
          if (pkg.name === "openclaw") {
            logger.info(`[tracectrl] Found OpenClaw install at ${dir}`);
            return dir;
          }
        } catch {
          // not the right package.json, keep walking
        }
      }
      const parent = dirname(dir);
      if (parent === dir) break; // reached filesystem root
      dir = parent;
    }

    // Case 2: bin is in a node bin dir, sibling lib dir has node_modules/openclaw
    const binDir = dirname(realBin);
    const libCandidate = join(dirname(binDir), "lib", "node_modules", "openclaw");
    if (existsSync(join(libCandidate, "package.json"))) {
      logger.info(`[tracectrl] Found OpenClaw install at ${libCandidate}`);
      return libCandidate;
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Finds the diagnostics-otel api.js inside the OpenClaw install directory.
 * The stock extensions live at <openclaw>/dist/extensions/diagnostics-otel/api.js
 */
function findDiagnosticsOtelApi(openclawDir: string, logger: any): string | null {
  const stockPath = join(openclawDir, "dist", "extensions", "diagnostics-otel", "api.js");
  if (existsSync(stockPath)) {
    logger.info(`[tracectrl] Found diagnostics-otel api at ${stockPath}`);
    return stockPath;
  }

  // Fallback: search for any api.js under diagnostics-otel
  const extDir = join(openclawDir, "dist", "extensions");
  if (existsSync(extDir)) {
    try {
      const entries = readdirSync(extDir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory() && entry.name.includes("diagnostics")) {
          const candidate = join(extDir, entry.name, "api.js");
          if (existsSync(candidate)) {
            logger.info(`[tracectrl] Found diagnostics api at ${candidate}`);
            return candidate;
          }
        }
      }
    } catch {
      // ignore
    }
  }

  return null;
}

async function loadSdk(logger: any): Promise<boolean> {
  if (sdkLoaded) return onDiagnosticEvent !== null;
  sdkLoaded = true;

  // Strategy 1: Try well-known npm package names (may work in future SDK versions)
  const npmPaths = [
    "openclaw/plugin-sdk",
    "openclaw/plugin-sdk/diagnostic-runtime",
    "@openclaw/diagnostics-otel/api",
  ];

  for (const path of npmPaths) {
    try {
      // @ts-ignore — dynamic runtime imports
      const mod = await import(path);
      if (typeof mod.onDiagnosticEvent === "function") {
        onDiagnosticEvent = mod.onDiagnosticEvent;
        logger.info(`[tracectrl] Loaded onDiagnosticEvent from npm: ${path}`);
        return true;
      }
    } catch {
      // not available, try next
    }
  }

  // Strategy 2: Dynamically locate the OpenClaw install and import the stock
  // diagnostics-otel api.js which re-exports onDiagnosticEvent
  const openclawDir = findOpenClawInstallDir(logger);
  if (openclawDir) {
    const apiPath = findDiagnosticsOtelApi(openclawDir, logger);
    if (apiPath) {
      try {
        // Use file:// URL for ESM dynamic import compatibility
        const fileUrl = `file://${apiPath}`;
        // @ts-ignore — dynamic runtime import of absolute file path
        const mod = await import(fileUrl);
        if (typeof mod.onDiagnosticEvent === "function") {
          onDiagnosticEvent = mod.onDiagnosticEvent;
          logger.info(
            `[tracectrl] Loaded onDiagnosticEvent from stock plugin: ${apiPath}`
          );
          return true;
        }
        logger.warn(
          `[tracectrl] diagnostics-otel api.js loaded but onDiagnosticEvent not found in exports`
        );
      } catch (err) {
        logger.warn(
          `[tracectrl] Could not import diagnostics-otel api.js: ${err instanceof Error ? err.message : String(err)}`
        );
      }
    }
  }

  // Strategy 3: Fall back gracefully — hook-only mode
  logger.warn(
    "[tracectrl] onDiagnosticEvent not available — running in hook-only mode. " +
      "Enable the built-in diagnostics-otel plugin alongside tracectrl for " +
      "model.usage and message.processed spans."
  );
  return false;
}

// ---------------------------------------------------------------------------
// Main registration
// ---------------------------------------------------------------------------

export async function registerHooks(
  api: any,
  telemetry: TelemetryRuntime,
  config: TraceCtrlConfig
): Promise<void> {
  const { tracer, counters, histograms } = telemetry;
  const logger = api.logger;

  // -------------------------------------------------------------------
  // Strategy 1: Diagnostic events (richest telemetry — model usage, etc.)
  // -------------------------------------------------------------------

  const hasDiagnostics = await loadSdk(logger);
  if (hasDiagnostics && onDiagnosticEvent) {
    registerDiagnosticListeners(
      tracer,
      counters,
      histograms,
      config,
      logger
    );
  }

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
            attributes: {
              "tracectrl.diagnostic_events": hasDiagnostics
                ? "active"
                : "unavailable",
            },
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
              "tracectrl.message.from":
                event?.from ?? event?.senderId ?? "unknown",
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
    logger.info(
      "[tracectrl] Registered message_received hook (may not fire in all versions)"
    );
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
    logger.info(
      "[tracectrl] Registered agent_end hook (may not fire in all versions)"
    );
  } catch {
    // ignore
  }

  // -------------------------------------------------------------------
  // Periodic cleanup of stale session contexts (5 min TTL)
  // -------------------------------------------------------------------

  const cleanupInterval = setInterval(() => {
    const now = Date.now();
    for (const [key, ctx] of sessionContextMap) {
      if (now - ctx.startTime > 5 * 60 * 1000) {
        try {
          ctx.rootSpan.setStatus({ code: SpanStatusCode.OK });
          ctx.rootSpan.end();
        } catch {
          // ignore
        }
        sessionContextMap.delete(key);
      }
    }
  }, 60_000);

  // Allow the Node.js process to exit even if this timer is still running
  if (cleanupInterval.unref) {
    cleanupInterval.unref();
  }

  logger.info(
    `[tracectrl] All hooks registered (diagnostic_events=${hasDiagnostics ? "active" : "unavailable"})`
  );
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

  const unsubscribe = onDiagnosticEvent((evt: any) => {
    try {
      const type = evt?.type;

      // -- message.processed ------------------------------------------------
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

      // -- model.usage ------------------------------------------------------
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

      // -- webhook.received -------------------------------------------------
      if (type === "webhook.received") {
        counters.messagesReceived.add(1, {
          "tracectrl.channel": evt.channel ?? "unknown",
        });
      }

      // -- webhook.error ----------------------------------------------------
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

      // -- session.stuck ----------------------------------------------------
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
