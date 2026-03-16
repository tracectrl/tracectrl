"""TraceCtrl AWS Strands instrumentor — wraps OpenInference span processor.

Note: Unlike the other 4 frameworks, the Strands OI package provides a
SpanProcessor (`StrandsAgentsToOpenInferenceProcessor`) rather than an
Instrumentor subclass. This wrapper adapts it to the same interface.
"""

from openinference.instrumentation.strands_agents import StrandsAgentsToOpenInferenceProcessor
from tracectrl.processor import TraceCtrlSpanProcessor
from tracectrl.config import get_tracer_provider


class StrandsInstrumentor:
    _instrumented = False
    _tc_processor = None

    def instrument(self, *, tracer_provider=None, **kwargs):
        if self._instrumented:
            return
        tp = tracer_provider or get_tracer_provider()
        # Strands uses a processor pattern, not an instrumentor pattern
        tp.add_span_processor(StrandsAgentsToOpenInferenceProcessor())
        self.__class__._tc_processor = TraceCtrlSpanProcessor()
        tp.add_span_processor(self.__class__._tc_processor)
        self.__class__._instrumented = True

    def uninstrument(self):
        # Strands processor doesn't support removal; shut down TraceCtrl processor
        if self.__class__._tc_processor:
            self.__class__._tc_processor.shutdown()
        self.__class__._instrumented = False

    @property
    def instrumented(self):
        return self._instrumented
