import { initTelemetry } from "./telemetry.js";
import { registerHooks } from "./hooks.js";
import { parseConfig } from "./config.js";

// OpenClaw plugin entry — exported as a plain object.
// OpenClaw's plugin loader accepts both definePluginEntry() and plain objects.
// The register() method can be async — the loader awaits it.
export default {
  id: "tracectrl",
  name: "TraceCtrl",
  description: "Security observability for AI agents",
  async register(api: any) {
    const config = parseConfig(api.config);
    const logger = api.logger;

    logger.info(
      `[tracectrl] Initializing — endpoint=${config.endpoint}, service=${config.serviceName}`
    );

    const telemetry = initTelemetry(config, logger);
    await registerHooks(api, telemetry, config);

    logger.info("[tracectrl] Plugin registered successfully");
  },
};
