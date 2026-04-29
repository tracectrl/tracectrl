"""Environment-based configuration and TracerProvider setup."""

import logging
import os
import threading
from urllib.parse import urlparse
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

logger = logging.getLogger("tracectrl")

_configured = False
_tracer_provider: TracerProvider | None = None
_init_lock = threading.Lock()


class TraceCtrlConfig:
    def __init__(self):
        self.endpoint = os.getenv("TRACECTRL_ENDPOINT", "http://localhost:4317")
        self.service_name = os.getenv("TRACECTRL_SERVICE_NAME", "tracectrl-agent")
        self.api_key = os.getenv("TRACECTRL_API_KEY")
        self.batch_delay_ms = int(os.getenv("TRACECTRL_BATCH_DELAY_MS", "1000"))
        self.max_batch_size = int(os.getenv("TRACECTRL_MAX_BATCH_SIZE", "512"))
        self.fail_silently = os.getenv("TRACECTRL_FAIL_SILENTLY", "true").lower() == "true"


_config = TraceCtrlConfig()


def _normalize_endpoint(endpoint: str) -> tuple[str, bool]:
    """Strip scheme from endpoint for gRPC and determine TLS mode."""
    parsed = urlparse(endpoint)
    insecure = parsed.scheme != "https"
    # gRPC exporter expects host:port without scheme
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if not insecure else 4317)
    return f"{host}:{port}", insecure


def configure(
    endpoint: str | None = None,
    service_name: str | None = None,
    api_key: str | None = None,
    fail_silently: bool | None = None,
):
    """Programmatic configuration. Must be called before instrument()."""
    global _config, _configured, _tracer_provider
    if endpoint:
        _config.endpoint = endpoint
    if service_name:
        _config.service_name = service_name
    if api_key:
        _config.api_key = api_key
    if fail_silently is not None:
        _config.fail_silently = fail_silently
    # Shut down existing provider to avoid thread leaks
    with _init_lock:
        if _tracer_provider is not None:
            try:
                _tracer_provider.shutdown()
            except Exception:
                pass
            _tracer_provider = None
        _configured = False


def get_tracer_provider() -> TracerProvider:
    """Returns (and lazily creates) the shared TracerProvider. Thread-safe."""
    global _tracer_provider, _configured
    if _tracer_provider and _configured:
        return _tracer_provider

    with _init_lock:
        # Double-check after acquiring lock
        if _tracer_provider and _configured:
            return _tracer_provider

        resource = Resource.create({"service.name": _config.service_name})

        headers = {}
        if _config.api_key:
            headers["Authorization"] = f"Bearer {_config.api_key}"

        normalized_endpoint, insecure = _normalize_endpoint(_config.endpoint)

        try:
            exporter = OTLPSpanExporter(
                endpoint=normalized_endpoint,
                headers=headers,
                insecure=insecure,
            )
        except Exception as e:
            if _config.fail_silently:
                logger.warning(f"TraceCtrl: failed to create exporter: {e}")
                exporter = None
            else:
                raise

        _tracer_provider = TracerProvider(resource=resource)
        if exporter:
            _tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    exporter,
                    schedule_delay_millis=_config.batch_delay_ms,
                    max_export_batch_size=_config.max_batch_size,
                )
            )
        # Auto-install the agent-prompt stamper so any subsequent tag_agent()
        # calls take effect without requiring the user to wire processors.
        try:
            from tracectrl.agent_tagging import _ensure_processor_installed
            _ensure_processor_installed(_tracer_provider)
        except Exception:
            logger.debug("could not install SystemPromptStamper", exc_info=True)
        trace.set_tracer_provider(_tracer_provider)
        _configured = True

        # Quick reachability check — warn if the collector is down
        if exporter and not _check_endpoint_reachable(_config.endpoint):
            logger.warning(
                f"TraceCtrl: OTel endpoint {_config.endpoint} is not reachable. "
                "Spans will not be exported. Run 'tracectrl doctor' to diagnose."
            )

        return _tracer_provider


def _check_endpoint_reachable(endpoint: str) -> bool:
    """Quick check if the OTel endpoint is reachable."""
    import urllib.request
    import urllib.error

    try:
        check_url = endpoint
        if not check_url.startswith("http"):
            check_url = f"http://{endpoint}"
        req = urllib.request.Request(check_url, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return True
    except urllib.error.HTTPError:
        return True  # 405 = endpoint exists
    except Exception:
        return False
