from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Literal
from urllib.parse import quote


DEFAULT_CORTEX_MEM_URL = "http://localhost:8085"
DEFAULT_TENANT_ID = "tenant_claw"


class CortexMemError(RuntimeError):
    pass


def sanitize_session_id(value: str, *, fallback: str = "default") -> str:
    """
    Convert an arbitrary label into a URL-safe session_id.

    Notes:
    - Avoid slashes. Session IDs are used as path segments in the cortex-mem API.
    - Keep it stable (used as the long-term thread key).
    """
    value = (value or "").strip()
    if not value:
        return fallback
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._-")
    return value or fallback


class CortexMemClient:
    def __init__(
        self,
        service_url: str | None = None,
        *,
        tenant_id: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.service_url = (service_url or os.getenv("CORTEX_MEM_URL") or DEFAULT_CORTEX_MEM_URL).rstrip("/")
        self.tenant_id = tenant_id or os.getenv("MEMCLAW_TENANT_ID") or DEFAULT_TENANT_ID
        self.timeout_s = float(timeout_s or os.getenv("MEMCLAW_HTTP_TIMEOUT_S") or 15.0)
        self._active_tenant_id: str | None = None

    # ==================== Tenant ====================

    def switch_tenant(self, tenant_id: str | None = None) -> None:
        tenant_id = tenant_id or self.tenant_id
        if not tenant_id:
            return
        if self._active_tenant_id == tenant_id:
            return

        last_error: Exception | None = None
        for path in ("/api/v2/tenants/switch", "/api/v2/tenants/tenants/switch"):
            try:
                response = self._request_json(
                    "POST",
                    path,
                    payload={"tenant_id": tenant_id},
                    allow_http_error=False,
                )
                if response.get("success") is False:
                    raise CortexMemError(response.get("error") or "Switch tenant failed")
                self._active_tenant_id = tenant_id
                return
            except Exception as exc:
                last_error = exc
                continue

        raise CortexMemError(f"Failed to switch tenant to {tenant_id!r}: {last_error}")

    # ==================== Session Management ====================

    def add_message(
        self,
        session_id: str,
        *,
        content: str,
        role: Literal["user", "assistant", "system"] = "user",
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        self.switch_tenant()
        safe_session_id = quote(session_id, safe="")
        payload: dict[str, Any] = {"role": role, "content": content}
        if metadata is not None:
            payload["metadata"] = metadata

        response = self._request_json(
            "POST",
            f"/api/v2/sessions/{safe_session_id}/messages",
            payload=payload,
        )
        if not response.get("success") or response.get("data") is None:
            raise CortexMemError(response.get("error") or "Add message failed")
        return response["data"]

    def commit_session(self, session_id: str) -> Any:
        self.switch_tenant()
        safe_session_id = quote(session_id, safe="")
        response = self._request_json(
            "POST",
            f"/api/v2/sessions/{safe_session_id}/close",
            payload={},
        )
        if not response.get("success") or response.get("data") is None:
            raise CortexMemError(response.get("error") or "Commit session failed")
        return response["data"]

    # ==================== Search ====================

    def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        limit: int = 10,
        min_score: float = 0.6,
        return_layers: list[Literal["L0", "L1", "L2"]] | None = None,
    ) -> list[dict[str, Any]]:
        self.switch_tenant()
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "min_score": min_score,
            "return_layers": return_layers or ["L0"],
        }
        if scope:
            payload["thread"] = scope

        response = self._request_json("POST", "/api/v2/search", payload=payload)
        if not response.get("success") or response.get("data") is None:
            raise CortexMemError(response.get("error") or "Search failed")
        return list(response["data"])

    # ==================== Internal ====================

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        allow_http_error: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.service_url}{path}"
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            if not allow_http_error:
                raise
        except Exception as exc:
            raise CortexMemError(f"Request failed: {exc}") from exc

        try:
            decoded = raw.decode("utf-8") if raw else "{}"
            return json.loads(decoded)
        except Exception as exc:
            preview = raw[:200].decode("utf-8", errors="replace")
            raise CortexMemError(f"Invalid JSON from {url} (HTTP {status}): {preview}") from exc
