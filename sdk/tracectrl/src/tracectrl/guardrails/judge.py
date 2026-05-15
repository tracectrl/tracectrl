"""Judge LLM invocation with structured output parsing.

Supports two backends, picked by inspecting the `judge_llm` argument:

  - **Strands BedrockModel** (default for everything we don't recognise) —
    Calls boto3's `bedrock-runtime.converse` directly with a single-tool
    schema. We bind to boto3 instead of going through Strands'
    `BedrockModel.structured_output` because that public surface is async
    and its method names have shifted across versions.

  - **Strands GeminiModel** — Calls Google's genai SDK via the client
    object embedded in the GeminiModel. We force structured output by
    setting `response_mime_type="application/json"` plus an OpenAPI-style
    `response_schema`. No AWS credentials required — the same
    `GOOGLE_API_KEY` the workshop's agents are using is enough.

Both backends produce a `JudgeResult` directly so the retry loop in
`invoke_judge` is provider-agnostic.

On invocation/parse failure we re-prompt once; a second failure defaults to
`pass=true` (a broken judge must not spam violation alerts).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Single tool the judge is forced to call. Schema matches the PRD exactly.
_JUDGE_TOOL_NAME = "record_decision"
_JUDGE_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "pass": {
            "type": "boolean",
            "description": "true if the output satisfies the guardrail; false if it violates.",
        },
        "reason": {
            "type": "string",
            "description": "One-sentence explanation of the decision.",
        },
        "evidence": {
            "type": ["string", "null"],
            "description": "Verbatim snippet that triggered a fail; null if pass.",
        },
    },
    "required": ["pass", "reason"],
}


# Gemini's response_schema lives under the Vertex / OpenAPI dialect — it
# doesn't accept union types like ["string", "null"]. We drop `evidence` from
# `required` so the model can omit it on a pass; if it sets it to an empty
# string, the parser below normalises to None for symmetry with the Bedrock
# JudgeResult shape.
_GEMINI_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "pass": {
            "type": "boolean",
            "description": "true if the output satisfies the guardrail; false if it violates.",
        },
        "reason": {
            "type": "string",
            "description": "One-sentence explanation of the decision.",
        },
        "evidence": {
            "type": "string",
            "description": "Verbatim snippet that triggered a fail; empty string if pass.",
        },
    },
    "required": ["pass", "reason"],
}


@dataclass
class JudgeResult:
    passed: bool
    reason: str
    evidence: Optional[str]


def invoke_judge(judge_llm: Any, prompt: str) -> JudgeResult:
    """Dispatch to the right backend (Bedrock or Gemini), retry once on failure,
    default-pass on a second failure.

    Picking the backend by type means existing BedrockModel callers see ZERO
    behavioural change — the dispatch falls through to the Bedrock path
    untouched. GeminiModel callers go to a parallel Gemini path that doesn't
    need AWS credentials.
    """
    invoker = _resolve_invoker(judge_llm)
    last_err: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            return invoker(judge_llm, prompt, attempt=attempt)
        except Exception as exc:  # noqa: BLE001 — broad on purpose; retry once
            last_err = exc
            logger.warning(
                "judge attempt %d failed via %s: %s",
                attempt,
                getattr(invoker, "__name__", "unknown"),
                exc,
            )
            continue

    logger.warning(
        "guardrail judge failed to produce valid JSON twice; defaulting to pass (last error: %s)",
        last_err,
    )
    return JudgeResult(passed=True, reason="judge parse failed; defaulted to pass", evidence=None)


def _resolve_invoker(judge_llm: Any):
    """Pick the backend by type. Defaults to Bedrock for backward compat —
    anything not specifically recognised falls through to the original path."""
    if _is_gemini_model(judge_llm):
        return _invoke_gemini_judge
    return _invoke_bedrock_judge


def _is_gemini_model(judge_llm: Any) -> bool:
    """True only for a real Strands GeminiModel instance. Lazy-imports so
    SDK callers without `strands.models.gemini` (older Strands, custom
    builds) keep working — they just always go to the Bedrock path."""
    try:
        from strands.models.gemini import GeminiModel  # type: ignore
    except ImportError:
        return False
    return isinstance(judge_llm, GeminiModel)


def _invoke_bedrock_judge(judge_llm: Any, prompt: str, *, attempt: int) -> JudgeResult:
    """Bedrock path — uses boto3.bedrock-runtime.converse with tool-forcing.

    This is the original implementation, refactored only to return a
    JudgeResult directly so it shares the dispatcher's retry shape with the
    Gemini path. The underlying `_call_model` + `_parse_judge_response` are
    unchanged.
    """
    raw = _call_model(judge_llm, prompt, attempt=attempt)
    return _parse_judge_response(raw)


def _resolve_bedrock_model(judge_llm: Any) -> tuple[str, str]:
    """Pull (model_id, region) from a Strands BedrockModel or from explicit config."""
    # Strands BedrockModel stores config in `_config` / `get_config()`.
    config: dict = {}
    if hasattr(judge_llm, "get_config"):
        try:
            cfg = judge_llm.get_config()
            if isinstance(cfg, dict):
                config = cfg
        except Exception:  # noqa: BLE001
            pass
    if not config and hasattr(judge_llm, "config"):
        c = judge_llm.config
        if isinstance(c, dict):
            config = c
    model_id = (
        config.get("model_id")
        or getattr(judge_llm, "model_id", None)
        or getattr(judge_llm, "model", None)
    )
    region = (
        config.get("region_name")
        or getattr(judge_llm, "region_name", None)
        or "us-east-1"
    )
    if not model_id:
        raise RuntimeError(f"could not extract model_id from judge_llm: {type(judge_llm).__name__}")
    return model_id, region


def _call_model(judge_llm: Any, prompt: str, *, attempt: int) -> Any:
    """Call Bedrock converse with tool-use forcing the JSON schema.

    boto3 is bundled with every AWS Lambda / Strands deploy; importing it lazily
    here keeps the SDK's import-time footprint clean.
    """
    import boto3

    model_id, region = _resolve_bedrock_model(judge_llm)

    system = (
        "You are an automated guardrail judge. You MUST call the "
        f"`{_JUDGE_TOOL_NAME}` tool with your decision. Do not answer in plain text."
    )
    if attempt == 2:
        system += " Your previous response was not valid JSON; respond by calling the tool exactly."

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        system=[{"text": system}],
        toolConfig={
            "tools": [{
                "toolSpec": {
                    "name": _JUDGE_TOOL_NAME,
                    "description": "Record the guardrail pass/fail decision.",
                    "inputSchema": {"json": _JUDGE_TOOL_SCHEMA},
                }
            }],
            # `any` forces the model to call SOME tool; combined with a single
            # tool in the list this guarantees we get our schema back.
            "toolChoice": {"any": {}},
        },
    )
    return response


def _parse_judge_response(raw: Any) -> JudgeResult:
    """Extract the structured decision from a Bedrock converse response."""
    payload: Optional[dict] = None

    # Bedrock converse response shape: {output: {message: {content: [{toolUse: {input: {...}}}]}}}
    if isinstance(raw, dict):
        output = raw.get("output") or {}
        message = output.get("message") if isinstance(output, dict) else None
        if isinstance(message, dict):
            for block in message.get("content", []) or []:
                if isinstance(block, dict) and "toolUse" in block:
                    payload = block["toolUse"].get("input")
                    break
        if payload is None:
            # Some intermediaries flatten this — try direct keys.
            payload = raw.get("input") or raw.get("toolUse", {}).get("input")

    # Plain text fallback — try to find a JSON object in the string.
    if payload is None:
        text = _stringify(raw)
        payload = _extract_json_object(text)

    if not isinstance(payload, dict):
        raise ValueError(f"could not extract JSON object from judge response: {raw!r}")

    if "pass" not in payload or "reason" not in payload:
        raise ValueError(f"judge JSON missing required keys: {payload!r}")

    return JudgeResult(
        passed=bool(payload["pass"]),
        reason=str(payload.get("reason", "")),
        evidence=(str(payload["evidence"]) if payload.get("evidence") else None),
    )


def _stringify(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return json.dumps(raw)
    text = getattr(raw, "text", None)
    if isinstance(text, str):
        return text
    return str(raw)


def _extract_json_object(text: str) -> Optional[dict]:
    """Find the first balanced top-level JSON object in `text`."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------


def _invoke_gemini_judge(judge_llm: Any, prompt: str, *, attempt: int) -> JudgeResult:
    """Gemini path — uses the `google.genai` client embedded in Strands'
    GeminiModel. No AWS credentials required.

    We force structured output via `response_mime_type='application/json'`
    plus an OpenAPI-style schema (`_GEMINI_JUDGE_SCHEMA`). On the second
    attempt we sharpen the system instruction so the model recovers from
    whatever malformed-JSON cause the first attempt hit.
    """
    client = _resolve_gemini_client(judge_llm)

    model_id = _resolve_gemini_model_id(judge_llm)

    system_text = (
        "You are an automated guardrail judge. Respond with ONLY a JSON "
        "object matching the schema {pass: bool, reason: string, evidence: "
        "string}. On pass, evidence may be an empty string. On fail, "
        "evidence must be the verbatim snippet that triggered the fail "
        "(max ~200 chars). Do not include any text outside the JSON."
    )
    if attempt == 2:
        system_text += (
            " Your previous response was not parseable. Return strict JSON "
            "with no preamble, no markdown fences, no commentary."
        )

    # Lazy import — keeps SDK import-time clean for callers that never use Gemini.
    from google.genai import types as genai_types  # type: ignore

    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_GEMINI_JUDGE_SCHEMA,
            system_instruction=system_text,
            # Low temperature — judges should be near-deterministic.
            temperature=0.0,
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("gemini judge returned empty body")

    payload = json.loads(text)

    if "pass" not in payload or "reason" not in payload:
        raise ValueError(f"gemini judge JSON missing required keys: {payload!r}")

    # Normalise empty-string evidence to None so downstream consumers can
    # treat 'no evidence' uniformly regardless of backend. Bedrock's path
    # already does this via the explicit "null" union type.
    raw_evidence = payload.get("evidence")
    evidence = str(raw_evidence) if raw_evidence else None

    return JudgeResult(
        passed=bool(payload["pass"]),
        reason=str(payload.get("reason", "")),
        evidence=evidence,
    )


def _resolve_gemini_client(judge_llm: Any) -> Any:
    """Return a cached `google.genai.Client` for this judge_llm, building it
    once and stashing it on the judge_llm instance.

    Strands' `GeminiModel` does NOT expose a `.client` attribute — it stores
    `_custom_client` + `client_args` and builds a fresh `genai.Client` on
    every request via `_get_client()`. Before this cache, every guardrail
    evaluation was constructing a brand new `genai.Client` (with its own
    httpx pool and credential setup), which under sustained load against
    the Gemini preview models has been observed to stall judge calls and
    starve subsequent agent invocations of FDs. One client per judge_llm
    is enough — `genai.Client` is documented as not safe to share across
    asyncio event loops, but we only call it from the synchronous path on
    a dedicated thread, so a single instance is correct here.
    """
    cached = getattr(judge_llm, "_tracectrl_genai_client", None)
    if cached is not None:
        return cached
    # If the GeminiModel was constructed with an injected client, honour it.
    injected = getattr(judge_llm, "_custom_client", None)
    if injected is not None:
        return injected
    client_args = getattr(judge_llm, "client_args", None) or {}
    try:
        from google import genai  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "GeminiModel passed as judge_llm but `google-genai` is not "
            "installed. `pip install google-genai`."
        ) from e
    client = genai.Client(**client_args)
    try:
        judge_llm._tracectrl_genai_client = client
    except Exception:  # noqa: BLE001 — frozen dataclasses etc.
        pass
    return client


def _resolve_gemini_model_id(judge_llm: Any) -> str:
    """Extract model_id from a Strands GeminiModel. Mirrors the
    Bedrock-side `_resolve_bedrock_model` shape but returns just the id —
    Gemini doesn't need a region."""
    config: dict = {}
    if hasattr(judge_llm, "get_config"):
        try:
            cfg = judge_llm.get_config()
            if isinstance(cfg, dict):
                config = cfg
        except Exception:  # noqa: BLE001
            pass
    if not config and hasattr(judge_llm, "config"):
        c = judge_llm.config
        if isinstance(c, dict):
            config = c
    model_id = (
        config.get("model_id")
        or getattr(judge_llm, "model_id", None)
        or getattr(judge_llm, "model", None)
    )
    if not model_id:
        raise RuntimeError(
            f"could not extract model_id from GeminiModel: {type(judge_llm).__name__}"
        )
    return model_id
