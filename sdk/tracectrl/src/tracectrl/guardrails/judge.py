"""Judge LLM invocation with structured output parsing.

Uses Bedrock's `converse` API directly via boto3. Strands' BedrockModel
wraps the same API, but its public surface is async (`structured_output`)
and the public method names have shifted between versions, so binding to
boto3 directly is far more stable. We extract `model_id` + `region` from
the BedrockModel object and call `bedrock-runtime.converse` ourselves.

On parse failure we re-prompt once; a second failure is treated as
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


@dataclass
class JudgeResult:
    passed: bool
    reason: str
    evidence: Optional[str]


def invoke_judge(judge_llm: Any, prompt: str) -> JudgeResult:
    """Invoke the judge twice at most; second parse failure → conservative pass."""
    last_err: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            raw = _call_model(judge_llm, prompt, attempt=attempt)
            parsed = _parse_judge_response(raw)
            return parsed
        except Exception as exc:  # noqa: BLE001 — broad on purpose; retry once
            last_err = exc
            logger.warning("judge attempt %d failed: %s", attempt, exc)
            continue

    logger.warning(
        "guardrail judge failed to produce valid JSON twice; defaulting to pass (last error: %s)",
        last_err,
    )
    return JudgeResult(passed=True, reason="judge parse failed; defaulted to pass", evidence=None)


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
