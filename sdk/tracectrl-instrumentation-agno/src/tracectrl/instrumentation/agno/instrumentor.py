"""TraceCtrl Agno instrumentor — wraps OpenInference."""

from openinference.instrumentation.agno import AgnoInstrumentor as _OIInstrumentor
from tracectrl.processor import TraceCtrlSpanProcessor
from tracectrl.config import get_tracer_provider


class AgnoInstrumentor:
    _instrumented = False
    _processor = None

    def instrument(self, *, tracer_provider=None, skip_dep_check=False):
        if self._instrumented:
            return
        tp = tracer_provider or get_tracer_provider()
        _OIInstrumentor().instrument(tracer_provider=tp, skip_dep_check=skip_dep_check)
        self.__class__._processor = TraceCtrlSpanProcessor()
        tp.add_span_processor(self.__class__._processor)
        self.__class__._instrumented = True

    def uninstrument(self):
        _OIInstrumentor().uninstrument()
        if self.__class__._processor:
            self.__class__._processor.shutdown()
        self.__class__._instrumented = False

    @property
    def instrumented(self):
        return self._instrumented
