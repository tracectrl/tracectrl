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
import { analyseToolCall, analyseMessageContent } from "./security.js";

// ---------------------------------------------------------------------------
// Types — these mirror the OpenClaw plugin SDK shapes we depend on.
// We declare minimal interfaces so the plugin compiles without importing
// the full OpenClaw type surface (which may not be present at build time).
// ---------------------------------------------------------------------------

interface PluginApi {
  on(event: string, priority: number, handler: (...args: any[]) => any): void;
  registerHook(event: string, handler: (...args: any[]) => any): void;
  logger: Logger;
}

interface Logger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

// ---------------------------------------------------------------------------
// Session context tracking
// ---------------------------------------------------------------------------

interface SessionTraceContext {
  rootSpan: Span;
  rootContext: Context;
  agentSpan?: Span;
  agentContext?: Context;
  startTime: number;
}

const sessionContextMap = new Map<string, SessionTraceContext>();

// Stale-context cleanup every 60 s — drop anything older than 5 minutes
const STALE_THRESHOLD_MS = 5 * 60 * 1000;
let cleanupTimer: ReturnType<typeof setInterval> | undefined;

function startCleanupLoop(logger: Logger): void {
  if (cleanupTimer !== undefined) return;
  cleanupTimer = setInterval(() => {
    const now = Date.now();
    for (const [key, ctx] of sessionContextMap) {
      if (now - ctx.startTime > STALE_THRESHOLD_MS) {
        try {
          ctx.agentSpan?.end();
          ctx.rootSpan.setStatus({ code: SpanStatusCode.ERROR, message: "stale context — cleaned up" });
          ctx.rootSpan.end();
        } catch {
          // swallow — best effort
        }
        sessionContextMap.delete(key);
        logger.warn(`[tracectrl] Cleaned up stale session context: ${key}`);
      }
    }
  }, 60_000);

  // Allow the Node process to exit even if the timer is still alive
  if (typeof cleanupTimer === "object" && "unref" in cleanupTimer) {
    cleanupTimer.unref();
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let unknownCounter = 0;
function sessionKey(event: Record<string, any>): string {
  const key = event.sessionKey ?? event.session_key ?? event.sessionId;
  if (key != null) return String(key);
  // Generate unique fallback to avoid session map collisions
  return `unknown-${Date.now()}-${++unknownCounter}`;
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + "..." : s;
}

function safeJsonStringify(val: unknown, maxLen: number): string {
  try {
    const raw = JSON.stringify(val);
    return truncate(raw ?? "", maxLen);
  } catch {
    return "<unserializable>";
  }
}

// ---------------------------------------------------------------------------
// Hook registration
// ---------------------------------------------------------------------------

export function registerHooks(
  api: PluginApi,
  telemetry: TelemetryRuntime,
  config: TraceCtrlConfig
): void {
  const { tracer, counters, histograms } = telemetry;
  const logger = api.logger;

  startCleanupLoop(logger);

  // -----------------------------------------------------------------------
  // 1. message_received  (priority 100)
  // -----------------------------------------------------------------------
  api.on("message_received", 100, (event: Record<string, any>) => {
    try {
      const key = sessionKey(event);
      const rootSpan = tracer.startSpan("tracectrl.request", {
        kind: SpanKind.SERVER,
        attributes: {
          "tracectrl.channel": String(event.channel ?? "unknown"),
          "tracectrl.session.key": key,
          "tracectrl.message.from": String(event.from ?? event.role ?? "user"),
          "tracectrl.message.direction": "inbound",
        },
      });

      const rootCtx = trace.setSpan(context.active(), rootSpan);

      if (config.captureContent && typeof event.text === "string") {
        rootSpan.setAttribute(
          "tracectrl.message.text",
          truncate(event.text, 2000)
        );
        // Check for prompt injection in inbound content
        analyseMessageContent(event.text, rootSpan, telemetry);
      }

      sessionContextMap.set(key, {
        rootSpan,
        rootContext: rootCtx,
        startTime: Date.now(),
      });

      counters.messagesReceived.add(1, { "tracectrl.session.key": key });
    } catch (err) {
      logger.error(
        `[tracectrl] message_received hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  // -----------------------------------------------------------------------
  // 2. before_agent_start  (priority 90)
  // -----------------------------------------------------------------------
  api.on("before_agent_start", 90, (event: Record<string, any>) => {
    try {
      const key = sessionKey(event);
      const session = sessionContextMap.get(key);
      if (!session) {
        logger.warn(
          `[tracectrl] before_agent_start — no root context for session ${key}`
        );
        return undefined;
      }

      const agentSpan = tracer.startSpan(
        "tracectrl.agent.turn",
        {
          kind: SpanKind.INTERNAL,
          attributes: {
            "tracectrl.agent.id": String(event.agentId ?? event.agent_id ?? "default"),
            "tracectrl.session.key": key,
            "tracectrl.agent.model": String(event.model ?? "unknown"),
          },
        },
        session.rootContext
      );

      const agentCtx = trace.setSpan(session.rootContext, agentSpan);
      session.agentSpan = agentSpan;
      session.agentContext = agentCtx;
    } catch (err) {
      logger.error(
        `[tracectrl] before_agent_start hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  // -----------------------------------------------------------------------
  // 3. tool_result_persist  (priority -100, SYNCHRONOUS)
  // -----------------------------------------------------------------------
  api.on("tool_result_persist", -100, (event: Record<string, any>) => {
    let toolSpan: any = undefined;
    try {
      const key = sessionKey(event);
      const session = sessionContextMap.get(key);
      const parentCtx = session?.agentContext ?? session?.rootContext ?? context.active();

      const toolName = String(event.toolName ?? event.tool_name ?? "unknown");
      const toolCallId = String(event.callId ?? event.call_id ?? "");

      toolSpan = tracer.startSpan(
        `tracectrl.tool.${toolName}`,
        {
          kind: SpanKind.INTERNAL,
          attributes: {
            "tracectrl.tool.name": toolName,
            "tracectrl.tool.call_id": toolCallId,
            "tracectrl.tool.is_synthetic": Boolean(event.isSynthetic ?? event.is_synthetic ?? false),
            "tracectrl.session.key": key,
          },
        },
        parentCtx
      );

      // Capture tool input preview
      let toolInputStr: string | undefined;
      if (config.captureContent && event.input !== undefined) {
        toolInputStr = safeJsonStringify(event.input, 1000);
        toolSpan.setAttribute("tracectrl.tool.input_preview", toolInputStr);
      } else if (event.input !== undefined) {
        toolInputStr = safeJsonStringify(event.input, 1000);
      }

      // Capture result metadata
      const content = event.content ?? event.result;
      if (Array.isArray(content)) {
        toolSpan.setAttribute("tracectrl.tool.result_parts", content.length);
        const totalChars = content.reduce((sum: number, part: any) => {
          if (typeof part === "string") return sum + part.length;
          if (typeof part?.text === "string") return sum + part.text.length;
          return sum;
        }, 0);
        toolSpan.setAttribute("tracectrl.tool.result_chars", totalChars);
      } else if (typeof content === "string") {
        toolSpan.setAttribute("tracectrl.tool.result_chars", content.length);
        toolSpan.setAttribute("tracectrl.tool.result_parts", 1);
      }

      // Check for errors
      const isError = Boolean(event.isError ?? event.is_error ?? false);
      if (isError) {
        toolSpan.setStatus({
          code: SpanStatusCode.ERROR,
          message: String(event.errorMessage ?? event.error ?? "tool error"),
        });
        counters.toolErrors.add(1, { "tracectrl.tool.name": toolName });
      }

      // Security analysis
      analyseToolCall(toolName, toolInputStr, toolSpan, telemetry);

      // Increment tool call counter
      counters.toolCalls.add(1, { "tracectrl.tool.name": toolName });
    } catch (err) {
      toolSpan?.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
      logger.error(
        `[tracectrl] tool_result_persist hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      toolSpan?.end();
    }
    return undefined;
  });

  // -----------------------------------------------------------------------
  // 4. agent_end  (priority -100)
  // -----------------------------------------------------------------------
  api.on("agent_end", -100, (event: Record<string, any>) => {
    try {
      const key = sessionKey(event);
      const session = sessionContextMap.get(key);
      if (!session) {
        logger.warn(`[tracectrl] agent_end — no context for session ${key}`);
        return undefined;
      }

      // Extract token usage
      const messages = event.messages ?? event.result?.messages ?? [];
      let inputTokens = 0;
      let outputTokens = 0;
      let cacheReadTokens = 0;
      let cacheWriteTokens = 0;

      if (Array.isArray(messages)) {
        for (const msg of messages) {
          const usage = msg?.usage ?? msg?.meta?.usage;
          if (usage) {
            inputTokens += Number(usage.input_tokens ?? usage.inputTokens ?? 0);
            outputTokens += Number(usage.output_tokens ?? usage.outputTokens ?? 0);
            cacheReadTokens += Number(usage.cache_read_input_tokens ?? usage.cacheReadTokens ?? 0);
            cacheWriteTokens += Number(usage.cache_creation_input_tokens ?? usage.cacheWriteTokens ?? 0);
          }
        }
      }

      // Also check top-level usage if present
      const topUsage = event.usage ?? event.result?.usage;
      if (topUsage) {
        inputTokens += Number(topUsage.input_tokens ?? topUsage.inputTokens ?? 0);
        outputTokens += Number(topUsage.output_tokens ?? topUsage.outputTokens ?? 0);
        cacheReadTokens += Number(topUsage.cache_read_input_tokens ?? topUsage.cacheReadTokens ?? 0);
        cacheWriteTokens += Number(topUsage.cache_creation_input_tokens ?? topUsage.cacheWriteTokens ?? 0);
      }

      const totalTokens = inputTokens + outputTokens;

      // Set attributes on agent span
      if (session.agentSpan) {
        session.agentSpan.setAttributes({
          "gen_ai.usage.input_tokens": inputTokens,
          "gen_ai.usage.output_tokens": outputTokens,
          "gen_ai.usage.total_tokens": totalTokens,
          "tracectrl.tokens.cache_read": cacheReadTokens,
          "tracectrl.tokens.cache_write": cacheWriteTokens,
          "gen_ai.response.model": String(event.model ?? event.result?.model ?? "unknown"),
          "tracectrl.agent.success": event.error == null || event.error === false,
        });

        // Set span error status if agent turn failed
        if (event.error != null && event.error !== false) {
          session.agentSpan.setStatus({
            code: SpanStatusCode.ERROR,
            message: String(event.error).slice(0, 200),
          });
        } else {
          session.agentSpan.setStatus({ code: SpanStatusCode.OK });
        }

        const durationMs = Date.now() - session.startTime;
        session.agentSpan.setAttribute("tracectrl.agent.duration_ms", durationMs);

        // Record histogram
        histograms.agentTurnDuration.record(durationMs, {
          "tracectrl.agent.model": String(event.model ?? "unknown"),
        });

        session.agentSpan.end();
      }

      // Update token counters
      if (totalTokens > 0) {
        counters.tokensTotal.add(totalTokens);
        counters.tokensPrompt.add(inputTokens);
        counters.tokensCompletion.add(outputTokens);
      }

      // End root span
      session.rootSpan.end();

      // Increment messages sent (the agent produced a response)
      counters.messagesSent.add(1, { "tracectrl.session.key": key });

      // Clean up
      sessionContextMap.delete(key);
    } catch (err) {
      logger.error(
        `[tracectrl] agent_end hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  // -----------------------------------------------------------------------
  // 5. Event-stream hooks via api.registerHook()
  // -----------------------------------------------------------------------

  // command:new
  api.registerHook("command:new", (event: Record<string, any>) => {
    try {
      const span = tracer.startSpan("tracectrl.session.new", {
        kind: SpanKind.INTERNAL,
        attributes: {
          "tracectrl.session.action": "new",
          "tracectrl.session.key": sessionKey(event),
          "tracectrl.command.source": String(event.source ?? "unknown"),
        },
      });
      span.end();
    } catch (err) {
      logger.error(
        `[tracectrl] command:new hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  // command:reset
  api.registerHook("command:reset", (event: Record<string, any>) => {
    try {
      const key = sessionKey(event);
      const span = tracer.startSpan("tracectrl.session.reset", {
        kind: SpanKind.INTERNAL,
        attributes: {
          "tracectrl.session.action": "reset",
          "tracectrl.session.key": key,
          "tracectrl.command.source": String(event.source ?? "unknown"),
        },
      });
      span.end();

      // Clean up any lingering session context
      const session = sessionContextMap.get(key);
      if (session) {
        try {
          session.agentSpan?.end();
          session.rootSpan.end();
        } catch {
          // swallow
        }
        sessionContextMap.delete(key);
      }
    } catch (err) {
      logger.error(
        `[tracectrl] command:reset hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  // command:stop
  api.registerHook("command:stop", (event: Record<string, any>) => {
    try {
      const key = sessionKey(event);
      const span = tracer.startSpan("tracectrl.session.stop", {
        kind: SpanKind.INTERNAL,
        attributes: {
          "tracectrl.session.action": "stop",
          "tracectrl.session.key": key,
          "tracectrl.command.source": String(event.source ?? "unknown"),
        },
      });
      span.end();

      // Clean up session context
      const session = sessionContextMap.get(key);
      if (session) {
        try {
          session.agentSpan?.end();
          session.rootSpan.setStatus({ code: SpanStatusCode.ERROR, message: "session stopped" });
          session.rootSpan.end();
        } catch {
          // swallow
        }
        sessionContextMap.delete(key);
      }
    } catch (err) {
      logger.error(
        `[tracectrl] command:stop hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  // gateway:startup
  api.registerHook("gateway:startup", (event: Record<string, any>) => {
    try {
      const span = tracer.startSpan("tracectrl.gateway.startup", {
        kind: SpanKind.SERVER,
        attributes: {
          "tracectrl.gateway.version": String(event.version ?? "unknown"),
          "tracectrl.gateway.pid": typeof event.pid === "number" ? event.pid : 0,
        },
      });
      span.end();
      logger.info("[tracectrl] Gateway startup span recorded");
    } catch (err) {
      logger.error(
        `[tracectrl] gateway:startup hook error: ${err instanceof Error ? err.message : String(err)}`
      );
    }
    return undefined;
  });

  logger.info("[tracectrl] All hooks registered");
}
