"""Tests for the dual-backend guardrail judge.

The judge module dispatches between Bedrock and Gemini based on the
`judge_llm` argument's type. These tests use mock objects so neither AWS
credentials nor a real Gemini API key are required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tracectrl.guardrails.judge import (
    JudgeResult,
    _is_gemini_model,
    _resolve_invoker,
    _resolve_gemini_client,
    _resolve_gemini_model_id,
    _invoke_bedrock_judge,
    _invoke_gemini_judge,
    invoke_judge,
)


# ---------------------------------------------------------------------------
# Dispatcher — picks the right backend based on judge_llm type
# ---------------------------------------------------------------------------


def test_dispatcher_falls_back_to_bedrock_for_unknown_judge():
    """Backward compat: anything that isn't a recognised GeminiModel goes to
    the Bedrock path. This is what protects existing BedrockModel callers
    from any behavioural change."""

    class _FakeBedrock:
        model_id = "anthropic.claude-3-haiku"
        region_name = "us-east-1"

    invoker = _resolve_invoker(_FakeBedrock())
    assert invoker is _invoke_bedrock_judge


def test_dispatcher_picks_gemini_for_strands_gemini_model():
    pytest.importorskip("strands.models.gemini")
    from strands.models.gemini import GeminiModel

    # Construct a GeminiModel without making a real API call. We pass a
    # dummy api_key so client construction works; we never actually invoke.
    gm = GeminiModel(
        client_args={"api_key": "dummy-key-for-test"},
        model_id="gemini-2.5-flash",
    )
    invoker = _resolve_invoker(gm)
    assert invoker is _invoke_gemini_judge


def test_is_gemini_model_returns_false_for_random_objects():
    assert _is_gemini_model(object()) is False
    assert _is_gemini_model(None) is False
    assert _is_gemini_model("a string") is False


# ---------------------------------------------------------------------------
# Gemini backend — invocation + parsing
# ---------------------------------------------------------------------------


@pytest.fixture
def _genai_installed():
    """Gemini path uses `google.genai`. Skip the gemini-specific tests
    when it isn't installed so the SDK still works (and tests still pass)
    in Bedrock-only environments."""
    pytest.importorskip("google.genai")


def test_gemini_invoke_parses_pass_response(_genai_installed):
    """Happy path: model returns valid JSON with pass=true; helper
    normalises an empty-string evidence to None to match Bedrock shape."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {"pass": True, "reason": "looks fine", "evidence": ""}
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    fake_gm = MagicMock()
    fake_gm._tracectrl_genai_client = mock_client  # short-circuit the cache
    fake_gm.get_config.return_value = {"model_id": "gemini-2.5-flash"}

    result = _invoke_gemini_judge(fake_gm, "some prompt", attempt=1)

    assert isinstance(result, JudgeResult)
    assert result.passed is True
    assert result.reason == "looks fine"
    assert result.evidence is None  # empty string normalised


def test_gemini_invoke_parses_fail_response_with_evidence(_genai_installed):
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {"pass": False, "reason": "PII detected", "evidence": "john@example.com"}
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    fake_gm = MagicMock()
    fake_gm._tracectrl_genai_client = mock_client  # short-circuit the cache
    fake_gm.get_config.return_value = {"model_id": "gemini-2.5-flash"}

    result = _invoke_gemini_judge(fake_gm, "check this", attempt=1)

    assert result.passed is False
    assert result.reason == "PII detected"
    assert result.evidence == "john@example.com"


def test_gemini_invoke_raises_on_missing_required_keys(_genai_installed):
    """If the model violates the schema (which can happen on borderline
    inputs), invoke_judge catches the ValueError and retries."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({"pass": True})  # missing 'reason'
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    fake_gm = MagicMock()
    fake_gm._tracectrl_genai_client = mock_client  # short-circuit the cache
    fake_gm.get_config.return_value = {"model_id": "gemini-2.5-flash"}

    with pytest.raises(ValueError, match="missing required keys"):
        _invoke_gemini_judge(fake_gm, "prompt", attempt=1)


def test_gemini_invoke_raises_on_empty_body(_genai_installed):
    mock_response = MagicMock()
    mock_response.text = ""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    fake_gm = MagicMock()
    fake_gm._tracectrl_genai_client = mock_client  # short-circuit the cache
    fake_gm.get_config.return_value = {"model_id": "gemini-2.5-flash"}

    with pytest.raises(ValueError, match="empty body"):
        _invoke_gemini_judge(fake_gm, "prompt", attempt=1)


def test_gemini_invoke_sharpens_system_instruction_on_retry(_genai_installed):
    """The retry's system_instruction must explicitly demand strict JSON
    — that's how we recover from the model returning a markdown fence on
    the first attempt."""
    captured_configs = []

    def capture(*args, **kwargs):
        captured_configs.append(kwargs.get("config"))
        mock = MagicMock()
        mock.text = json.dumps({"pass": True, "reason": "ok", "evidence": ""})
        return mock

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = capture

    fake_gm = MagicMock()
    fake_gm._tracectrl_genai_client = mock_client  # short-circuit the cache
    fake_gm.get_config.return_value = {"model_id": "gemini-2.5-flash"}

    _invoke_gemini_judge(fake_gm, "p", attempt=1)
    _invoke_gemini_judge(fake_gm, "p", attempt=2)

    sys1 = captured_configs[0].system_instruction
    sys2 = captured_configs[1].system_instruction
    assert "strict JSON" in sys2
    assert "strict JSON" not in sys1


# ---------------------------------------------------------------------------
# model_id resolution
# ---------------------------------------------------------------------------


def test_resolve_gemini_model_id_prefers_get_config():
    fake = MagicMock()
    fake.get_config.return_value = {"model_id": "from-config"}
    fake.model_id = "from-attr"  # should be ignored if get_config wins
    assert _resolve_gemini_model_id(fake) == "from-config"


def test_resolve_gemini_model_id_falls_through_to_attr():
    fake = MagicMock(spec=["model_id"])  # no get_config
    fake.model_id = "from-attr"
    assert _resolve_gemini_model_id(fake) == "from-attr"


def test_resolve_gemini_model_id_raises_if_nothing_available():
    fake = MagicMock(spec=[])
    with pytest.raises(RuntimeError, match="could not extract model_id"):
        _resolve_gemini_model_id(fake)


# ---------------------------------------------------------------------------
# Gemini client caching — one Client per judge_llm, not one per eval
# ---------------------------------------------------------------------------


def test_resolve_gemini_client_returns_cached_attr_when_set():
    """If the cache is populated, no Client is built. This is the hot path
    after the first eval — every subsequent eval should hit the cache."""
    fake = MagicMock(spec=["_tracectrl_genai_client"])
    cached = object()
    fake._tracectrl_genai_client = cached
    assert _resolve_gemini_client(fake) is cached


def test_resolve_gemini_client_prefers_strands_custom_client():
    """Strands stores an injected client on `_custom_client`. We honour it
    rather than constructing our own."""
    fake = MagicMock(spec=["_tracectrl_genai_client", "_custom_client"])
    fake._tracectrl_genai_client = None
    injected = object()
    fake._custom_client = injected
    assert _resolve_gemini_client(fake) is injected


def test_resolve_gemini_client_caches_constructed_client(_genai_installed):
    """A fresh judge_llm with only `client_args` should construct ONE
    client and stash it on the instance. Calling again returns the same."""
    fake = MagicMock(spec=["_tracectrl_genai_client", "_custom_client", "client_args"])
    fake._tracectrl_genai_client = None
    fake._custom_client = None
    fake.client_args = {"api_key": "dummy-key-for-test"}

    first = _resolve_gemini_client(fake)
    # Stashed on the instance.
    assert getattr(fake, "_tracectrl_genai_client", None) is first
    second = _resolve_gemini_client(fake)
    assert first is second


# ---------------------------------------------------------------------------
# End-to-end through `invoke_judge` (the public entry point)
# ---------------------------------------------------------------------------


def test_invoke_judge_retries_once_then_default_passes():
    """If both attempts blow up, invoke_judge logs and returns
    pass=true with a self-explanatory reason — a broken judge must not
    spam violation alerts."""
    fake = MagicMock()
    fake.model_id = "fake"
    fake.region_name = "us-east-1"

    # Patch the Bedrock invoker so both attempts raise.
    with patch(
        "tracectrl.guardrails.judge._invoke_bedrock_judge",
        side_effect=RuntimeError("simulated outage"),
    ):
        result = invoke_judge(fake, "any prompt")

    assert result.passed is True
    assert "default" in result.reason.lower() or "pass" in result.reason.lower()


def test_invoke_judge_succeeds_on_first_attempt_returns_real_verdict():
    fake = MagicMock()
    fake.model_id = "fake"
    fake.region_name = "us-east-1"

    expected = JudgeResult(passed=False, reason="bad output", evidence="snippet")
    with patch(
        "tracectrl.guardrails.judge._invoke_bedrock_judge",
        return_value=expected,
    ):
        result = invoke_judge(fake, "any prompt")

    assert result is expected
