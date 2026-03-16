"""TraceCtrl SDK — security-enriched OpenTelemetry for agentic AI."""

# Enable namespace package merging so tracectrl.instrumentation.*
# sub-packages installed separately are discoverable.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

__version__ = "0.1.0"

from tracectrl.config import configure  # noqa: F401
