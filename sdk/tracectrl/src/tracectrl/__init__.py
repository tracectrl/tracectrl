"""TraceCtrl SDK — security-enriched OpenTelemetry for agentic AI."""

# Enable namespace package merging so tracectrl.instrumentation.*
# sub-packages installed separately are discoverable.
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)

__version__ = "0.3.1"

from tracectrl.config import configure  # noqa: F401
from tracectrl.context import ingress  # noqa: F401
from tracectrl.agent_tagging import tag_agent, tag_agents  # noqa: F401
from tracectrl.protector import (  # noqa: F401
    GuardrailVerdict,
    check_input,
    check_output,
    guard,
)
