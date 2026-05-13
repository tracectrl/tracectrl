"""Guardrail registry API — list/per-agent endpoints, plus TraceCtrl Guards
(Protector Plus) configuration and test endpoints."""

import ipaddress
import logging
import socket
import time

import urllib.parse
import urllib.request
import urllib.error

from fastapi import APIRouter, HTTPException

from engine.db.guardrail_invocations import get_guardrail_invocations
from engine.db.guardrail_registry import get_guardrail_registry
from engine.db.protector_config import (
    PROTECTOR_GUARDRAILS,
    get_protector_config,
    redact_api_key,
    set_protector_config,
)
from engine.api.models import (
    GuardrailInvocation,
    GuardrailRegistration,
    ProtectorConfig,
    ProtectorConfigUpsert,
    ProtectorTestResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["guardrails"])


# ---------------------------------------------------------------------------
# Helpers — kept module-local so route handlers stay readable.
# ---------------------------------------------------------------------------


def _validate_external_url(url: str) -> str | None:
    """Sanity-check a user-supplied URL before we let urlopen touch it.

    Blocks loopback, private (RFC1918), link-local, and reserved hosts so a
    malicious or careless config can't turn the test endpoint into an SSRF
    probe against the cluster internals (ClickHouse, AWS metadata, etc.).
    Returns an error string if invalid, None if OK.

    KNOWN TOCTOU GAP (v2): we resolve DNS once here, then `urlopen` resolves
    independently milliseconds later. A DNS rebinding attacker who controls
    the resolution for `endpoint_url` can return a public IP during
    validation and a private one during the actual fetch, bypassing the
    check. Closing this requires resolving the address up-front and forcing
    `urlopen` to use the resolved IP (custom socket factory or pinning the
    `Host:` header). Acceptable for v1 single-tenant docker-compose
    (operators control the endpoint) but a real risk if this engine ever
    fronts multi-tenant traffic.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "invalid URL"
    if parsed.scheme not in ("http", "https"):
        return f"URL scheme must be http or https (got {parsed.scheme!r})"
    host = parsed.hostname
    if not host:
        return "URL is missing a host"
    # Resolve to all addresses and reject if any are non-public. We check all
    # records because a hostname can resolve to a private IP via /etc/hosts
    # or a DNS rebinding trick.
    try:
        addr_records = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        return f"DNS resolution failed: {e}"
    for record in addr_records:
        try:
            ip = ipaddress.ip_address(record[4][0])
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return f"host {host!r} resolves to a non-public address ({ip})"
    return None


@router.get("/guardrails", response_model=list[GuardrailRegistration])
async def list_guardrails(agent_id: str | None = None):
    try:
        return get_guardrail_registry(agent_id=agent_id)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/agents/{agent_id}/guardrails",
    response_model=list[GuardrailRegistration],
)
async def list_agent_guardrails(agent_id: str):
    try:
        return get_guardrail_registry(agent_id=agent_id)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/guardrails/invocations",
    response_model=list[GuardrailInvocation],
)
async def list_guardrail_invocations(
    agent_id: str,
    guardrail_name: str,
    limit: int = 50,
):
    """Recent `tracectrl.guardrail.evaluation` spans for a given guardrail.

    Returns pass/fail/error decisions ordered newest first. Powers the
    Recent Invocations panel in the guardrail detail drawer. Reads directly
    from `otel_traces` — does NOT depend on the pipeline tick.
    """
    if not agent_id or not guardrail_name:
        raise HTTPException(
            status_code=400, detail="agent_id and guardrail_name are required"
        )
    try:
        return get_guardrail_invocations(
            agent_id=agent_id,
            guardrail_name=guardrail_name,
            limit=limit,
        )
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# TraceCtrl Guards (Protector Plus) configuration
# ---------------------------------------------------------------------------


@router.get("/guardrails/protector-config", response_model=ProtectorConfig)
async def get_protector_config_redacted():
    """Public config read — api_key redacted to 'hOjm***vY2' for safe display in
    the Settings UI. The SDK uses the separate `/sdk` variant below to fetch
    the full key."""
    try:
        cfg = get_protector_config()
        if not cfg:
            return ProtectorConfig(
                endpoint_url="",
                api_key="",
                enabled_guardrails=[],
                updated_at=None,
            )
        return ProtectorConfig(
            endpoint_url=cfg["endpoint_url"],
            api_key=redact_api_key(cfg["api_key"]),
            enabled_guardrails=cfg["enabled_guardrails"],
            updated_at=cfg["updated_at"],
        )
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/guardrails/protector-config", response_model=ProtectorConfig)
async def put_protector_config(body: ProtectorConfigUpsert):
    """Upsert the global config. Returns the redacted form so the UI doesn't
    see its own freshly-sent api_key echoed back."""
    if not body.endpoint_url.strip():
        raise HTTPException(status_code=400, detail="endpoint_url is required")
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key is required")

    # Reject obviously-bad URLs at write time so /protector-test isn't the
    # only line of defense. Catches typos + protects against SSRF-shaped
    # config values being persisted.
    url_error = _validate_external_url(body.endpoint_url.strip().rstrip("/"))
    if url_error:
        raise HTTPException(status_code=400, detail=url_error)

    unknown = [g for g in body.enabled_guardrails if g not in PROTECTOR_GUARDRAILS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown guardrails: {unknown}; known: {sorted(PROTECTOR_GUARDRAILS)}",
        )

    try:
        written = set_protector_config(
            endpoint_url=body.endpoint_url.strip().rstrip("/"),
            api_key=body.api_key.strip(),
            enabled_guardrails=body.enabled_guardrails,
        )
        return ProtectorConfig(
            endpoint_url=written["endpoint_url"],
            api_key=redact_api_key(written["api_key"]),
            enabled_guardrails=written["enabled_guardrails"],
            updated_at=written["updated_at"],
        )
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/guardrails/protector-test", response_model=ProtectorTestResult)
async def post_protector_test():
    """Server-side health check against the stored Protector Plus endpoint.

    Hits `{endpoint}/api/protectorplus/v1/health` (no auth required per the
    Protector Plus docs) with a 5s timeout. The browser can't do this
    cross-origin reliably, hence proxying it here.

    Rejects non-public endpoints so this can't be turned into an SSRF probe.
    """
    cfg = get_protector_config()
    if not cfg or not cfg["endpoint_url"]:
        return ProtectorTestResult(
            ok=False, ms=0, error="No endpoint configured. Save settings first."
        )

    health_url = (
        cfg["endpoint_url"].rstrip("/") + "/api/protectorplus/v1/health"
    )
    validation_error = _validate_external_url(health_url)
    if validation_error:
        return ProtectorTestResult(ok=False, ms=0, error=validation_error)

    started = time.perf_counter()
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            ms = int((time.perf_counter() - started) * 1000)
            ok = 200 <= resp.status < 300
            return ProtectorTestResult(ok=ok, ms=ms, status_code=resp.status)
    except urllib.error.HTTPError as e:
        ms = int((time.perf_counter() - started) * 1000)
        return ProtectorTestResult(
            ok=False, ms=ms, status_code=e.code, error=f"HTTP {e.code} {e.reason}"
        )
    except urllib.error.URLError as e:
        ms = int((time.perf_counter() - started) * 1000)
        return ProtectorTestResult(ok=False, ms=ms, error=f"{e.reason}")
    except Exception as e:  # noqa: BLE001
        ms = int((time.perf_counter() - started) * 1000)
        return ProtectorTestResult(ok=False, ms=ms, error=str(e))


@router.get("/guardrails/protector-config/sdk", response_model=ProtectorConfigUpsert)
async def get_protector_config_for_sdk():
    """SDK fetch — full api_key included. Called once per agent at
    `with tracectrl.guardrails():` entry.

    NO AUTH in v1. The exposure boundary is deliberately owned by the
    deployment, not this route:
      - Docker compose default binds 8000 on the host but Docker's NAT means
        requests from the host arrive via the docker bridge IP, not
        127.0.0.1. An app-level "loopback only" check therefore breaks
        legitimate host→container SDK calls.
      - Operators who care about exposure should bind the published port to
        loopback only (e.g. `ports: ["127.0.0.1:8000:8000"]` in compose) or
        front the engine with an authenticated reverse proxy.
    Tenancy + a proper auth scheme is the v2 work.

    Returns an empty config if none is set so the SDK can no-op cleanly
    instead of erroring on a fresh install.
    """
    cfg = get_protector_config()
    if not cfg:
        return ProtectorConfigUpsert(
            endpoint_url="",
            api_key="",
            enabled_guardrails=[],
        )
    return ProtectorConfigUpsert(
        endpoint_url=cfg["endpoint_url"],
        api_key=cfg["api_key"],
        enabled_guardrails=cfg["enabled_guardrails"],
    )
