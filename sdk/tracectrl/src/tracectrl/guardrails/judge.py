"""Judge LLM invocation with structured output parsing.

We force the judge into a strict JSON schema via Bedrock tool-use. Tool-use is
the most portable "deterministic enough" path across Bedrock providers because
`converse_stream` does not give uniform logprobs. On parse failure we re-prompt
once; a second failure is treated as `pass=true` (we do not want a broken
judge to spam violation alerts).
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
            logger.debug("judge attempt %d failed: %s", attempt, exc)
            continue

    logger.warning(
        "guardrail judge failed to produce valid JSON twice; defaulting to pass (last error: %s)",
        last_err,
    )
    return JudgeResult(passed=True, reason="judge parse failed; defaulted to pass", evidence=None)


def _call_model(judge_llm: Any, prompt: str, *, attempt: int) -> Any:
    """Call the judge model via tool-use. Tries a few common Strands/Bedrock shapes.

    The Strands `BedrockModel` API surface is still consolidating; we try a small
    set of well-known method names rather than hard-binding to one. If none work
    we fall back to plain text generation and parse JSON from the response.
    """
    system = (
        "You are an automated guardrail judge. You MUST call the "
        f"`{_JUDGE_TOOL_NAME}` tool with your decision. Do not answer in plain text."
    )
    if attempt == 2:
        system += " Your previous response was not valid JSON; respond by calling the tool exactly."

    tool_spec = {
        "name": _JUDGE_TOOL_NAME,
        "description": "Record the guardrail pass/fail decision.",
        "input_schema": _JUDGE_TOOL_SCHEMA,
    }

    # Strategy 1: Strands BedrockModel converse-style call with tool config.
    converse = getattr(judge_llm, "converse", None)
    if callable(converse):
        try:
            return converse(
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                system=[{"text": system}],
                tool_config={"tools": [{"toolSpec": _to_bedrock_tool_spec(tool_spec)}]},
            )
        except TypeError:
            pass  # signature mismatch — fall through

    # Strategy 2: a generic `__call__` / `invoke` returning a string.
    for method_name in ("invoke", "__call__", "generate"):
        method = getattr(judge_llm, method_name, None)
        if callable(method):
            try:
                return method(f"{system}\n\n{prompt}\n\nReturn ONLY a JSON object matching: "
                              f"{json.dumps(_JUDGE_TOOL_SCHEMA)}")
            except TypeError:
                continue

    raise RuntimeError(f"unsupported judge_llm type: {type(judge_llm).__name__}")


def _to_bedrock_tool_spec(tool: dict) -> dict:
    """Translate our tool spec into Bedrock converse tool shape."""
    return {
        "name": tool["name"],
        "description": tool["description"],
        "inputSchema": {"json": tool["input_schema"]},
    }


def _parse_judge_response(raw: Any) -> JudgeResult:
    """Extract the structured decision from whatever shape the judge returned."""
    payload: Optional[dict] = None

    # Bedrock converse response shape.
    if isinstance(raw, dict):
        output = raw.get("output") or {}
        message = output.get("message") if isinstance(output, dict) else None
        if isinstance(message, dict):
            for block in message.get("content", []) or []:
                if isinstance(block, dict) and "toolUse" in block:
                    payload = block["toolUse"].get("input")
                    break
        if payload is None:
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
