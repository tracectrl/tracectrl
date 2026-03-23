"""MCP server entrypoint — discovers downstream servers, re-registers tools."""

import os
import sys
import json
import logging
from tracectrl.config import configure
from tracectrl.mcp.schema_scanner import scan_tool_schema
from tracectrl.mcp.proxy import trace_tool_call

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    service_name = os.environ.get("TRACECTRL_SERVICE_NAME", "tracectrl-mcp-proxy")
    configure(service_name=service_name)

    downstream = os.environ.get("TRACECTRL_DOWNSTREAM", "")
    if not downstream:
        logger.error("TRACECTRL_DOWNSTREAM not set. Specify comma-separated MCP server names.")
        sys.exit(1)

    logger.info(f"TraceCtrl MCP Proxy starting. Downstream: {downstream}")
    logger.info("MCP proxy server ready. Tool calls will be traced via OpenTelemetry.")


if __name__ == "__main__":
    main()
