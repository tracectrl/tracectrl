import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { initTelemetry } from "./telemetry.js";
import { registerHooks } from "./hooks.js";
import { parseConfig } from "./config.js";

export default definePluginEntry({
  id: "tracectrl",
  name: "TraceCtrl",
  description: "Security observability for AI agents",
  register(api) {
    const config = parseConfig(api.config);
    const logger = api.logger;

    logger.info(
      `[tracectrl] Initializing — endpoint=${config.endpoint}, service=${config.serviceName}`
    );

    const telemetry = initTelemetry(config, logger);
    registerHooks(api, telemetry, config);

    logger.info("[tracectrl] Plugin registered successfully");
  },
});
