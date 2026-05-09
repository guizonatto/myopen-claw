from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openclaw.cortex_mem import CortexMemClient, sanitize_session_id


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserPreferenceStore:
    """
    Generic user preference store with dual persistence:
    - Deterministic local JSON index (exact reads)
    - MemClaw append log (semantic recall / context sharing)
    """

    def __init__(self, *, path: str | None = None, mem_client: CortexMemClient | None = None) -> None:
        self.path = Path(path or os.getenv("USER_PREFERENCES_PATH", "/tmp/user_preferences.json"))
        self.mem = mem_client or CortexMemClient()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"users": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"users": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def set_preference(
        self,
        *,
        user_id: str,
        key: str,
        value: Any,
        domain: str = "general",
        source: str = "manual",
    ) -> dict[str, Any]:
        user_id = sanitize_session_id(user_id or "default-user")
        domain = (domain or "general").strip().lower()
        key = (key or "").strip().lower()
        if not key:
            raise ValueError("key is required")

        data = self._load()
        users = data.setdefault("users", {})
        user = users.setdefault(user_id, {})
        dom = user.setdefault(domain, {})
        dom[key] = {
            "value": value,
            "updated_at": _utcnow_iso(),
            "source": source,
        }
        self._save(data)
        self._append_memclaw_event(user_id=user_id, domain=domain, key=key, value=value, source=source)
        return dom[key]

    def get_preferences(self, *, user_id: str, domain: str | None = None) -> dict[str, Any]:
        user_id = sanitize_session_id(user_id or "default-user")
        data = self._load()
        users = data.get("users") or {}
        user = users.get(user_id) or {}
        if domain:
            normalized = domain.strip().lower()
            return {normalized: user.get(normalized, {})}
        return user

    def _append_memclaw_event(self, *, user_id: str, domain: str, key: str, value: Any, source: str) -> None:
        session_id = sanitize_session_id(f"user-preferences-{user_id}")
        content = (
            f"[user_preference] domain={domain} key={key} value={json.dumps(value, ensure_ascii=False)} "
            f"source={source}"
        )
        metadata = {
            "kind": "user_preference",
            "user_id": user_id,
            "domain": domain,
            "key": key,
            "source": source,
            "updated_at": _utcnow_iso(),
        }
        try:
            self.mem.add_message(session_id, role="assistant", content=content, metadata=metadata)
            self.mem.commit_session(session_id)
        except Exception:
            # Non-blocking: deterministic store is source of truth.
            pass
