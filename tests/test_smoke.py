"""Smoke tests — validates the repo scaffold and core SDK modules."""


def test_tracectrl_importable():
    import tracectrl
    assert tracectrl.__version__ == "0.1.0"


def test_schema_constants():
    from tracectrl.schema import TC_AGENT_ID, TC_TOOL_CATEGORY, OI_SPAN_KIND
    assert TC_AGENT_ID == "tracectrl.agent.id"
    assert TC_TOOL_CATEGORY == "tracectrl.tool.category"
    assert OI_SPAN_KIND == "openinference.span.kind"


def test_tool_category_inference():
    from tracectrl.inference import infer_tool_category
    assert infer_tool_category("send_email") == "email"
    assert infer_tool_category("execute_python") == "code_execution"
    assert infer_tool_category("http_request") == "external_api"
    assert infer_tool_category("write_file") == "file_system"
    assert infer_tool_category("vector_upsert") == "memory_write"
    assert infer_tool_category("search_docs") == "memory_read"
    assert infer_tool_category("ask_user") == "human_interaction"
    assert infer_tool_category("my_custom_tool") == "internal_api"


def test_session_management():
    from tracectrl.session import new_session, current_session_id
    sid = new_session()
    assert sid is not None
    assert len(sid) > 0
    assert current_session_id() == sid


def test_processor_importable():
    from tracectrl.processor import TraceCtrlSpanProcessor
    processor = TraceCtrlSpanProcessor()
    assert processor is not None


def test_config_importable():
    from tracectrl.config import TraceCtrlConfig
    config = TraceCtrlConfig()
    assert config.endpoint == "http://localhost:4317"
    assert config.service_name == "tracectrl-agent"
    assert config.fail_silently is True


def test_context_importable():
    from tracectrl.context import inject_trace_headers, extract_trace_headers  # noqa: F401
    headers = inject_trace_headers()
    assert isinstance(headers, dict)
