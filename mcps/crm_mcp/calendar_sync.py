from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen


CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _to_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _load_service_account_info() -> dict[str, Any]:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return json.loads(raw)

    path_value = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not path_value:
        raise RuntimeError("Configure GOOGLE_SERVICE_ACCOUNT_JSON ou GOOGLE_SERVICE_ACCOUNT_FILE.")

    path = Path(path_value).expanduser()
    if not path.exists():
        raise RuntimeError(f"Arquivo de service account não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _get_access_token() -> str:
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Dependências ausentes: instale google-auth e requests.") from exc

    info = _load_service_account_info()
    creds = service_account.Credentials.from_service_account_info(info, scopes=[CALENDAR_SCOPE])

    subject = os.environ.get("GOOGLE_CALENDAR_IMPERSONATE_USER")
    if subject:
        creds = creds.with_subject(subject)

    creds.refresh(GoogleAuthRequest())
    if not creds.token:
        raise RuntimeError("Falha ao gerar token de acesso do Google Calendar.")
    return creds.token


class GoogleCalendarClient:
    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = "https://www.googleapis.com/calendar/v3",
        transport: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._access_token = access_token
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    def _request_json(self, method: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport(method, url, payload)

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = UrlRequest(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(req, timeout=20) as resp:
                raw = resp.read(2_000_000)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raw_error = ""
            try:
                raw_error = exc.read().decode("utf-8", errors="replace")
            except Exception:
                raw_error = str(exc)
            raise RuntimeError(f"Google Calendar API {exc.code}: {raw_error}") from exc

    def upsert_event(self, calendar_id: str, event_payload: dict[str, Any], event_id: str | None = None) -> dict[str, Any]:
        quoted_calendar = quote(calendar_id, safe="")
        if event_id:
            quoted_event = quote(event_id, safe="")
            url = f"{self._base_url}/calendars/{quoted_calendar}/events/{quoted_event}"
            method = "PATCH"
        else:
            url = f"{self._base_url}/calendars/{quoted_calendar}/events"
            method = "POST"
        return self._request_json(method, url, event_payload)


def build_google_calendar_client_from_env() -> GoogleCalendarClient:
    token = _get_access_token()
    return GoogleCalendarClient(access_token=token)


def build_google_event_payload(
    contato: Any,
    task: Any,
    *,
    default_timezone: str | None = None,
    default_duration_minutes: int = 30,
) -> dict[str, Any]:
    timezone_name = default_timezone or os.environ.get("GOOGLE_CALENDAR_TIMEZONE", "America/Sao_Paulo")

    due_at: datetime = task.due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)

    reminder_at: datetime | None = getattr(task, "reminder_at", None)
    if reminder_at is not None and reminder_at.tzinfo is None:
        reminder_at = reminder_at.replace(tzinfo=timezone.utc)

    end_at = due_at + timedelta(minutes=default_duration_minutes)
    owner = (getattr(task, "owner", None) or "time comercial").strip()
    channel = (getattr(task, "channel", None) or "whatsapp").strip()
    objective = (getattr(task, "objective", None) or "Contato comercial").strip()
    nome = (getattr(contato, "nome", None) or "Contato").strip()
    empresa = (getattr(contato, "empresa", None) or "-").strip()
    whatsapp = (getattr(contato, "whatsapp", None) or "-").strip()
    email = (getattr(contato, "email", None) or "-").strip()
    task_id = str(getattr(task, "id", "-"))
    contato_id = str(getattr(contato, "id", "-"))

    description_lines = [
        f"Objetivo: {objective}",
        f"Canal: {channel}",
        f"Owner: {owner}",
        f"Contato: {nome}",
        f"Empresa: {empresa}",
        f"WhatsApp: {whatsapp}",
        f"Email: {email}",
        f"task_id: {task_id}",
        f"contato_id: {contato_id}",
    ]
    payload: dict[str, Any] = {
        "summary": f"CRM Follow-up: {nome}",
        "description": "\n".join(description_lines),
        "start": {"dateTime": _to_rfc3339(due_at), "timeZone": timezone_name},
        "end": {"dateTime": _to_rfc3339(end_at), "timeZone": timezone_name},
        "extendedProperties": {
            "private": {
                "crm_task_id": task_id,
                "crm_contact_id": contato_id,
                "crm_channel": channel,
            }
        },
    }

    if reminder_at is not None:
        reminder_minutes = int(max(0, (due_at - reminder_at).total_seconds() // 60))
        payload["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        }

    return payload


def _row_to_namespace(row: Any) -> tuple[Any, Any, Any]:
    """Suporta tanto tuple/list retornado pelo SQLAlchemy quanto objetos compostos de testes."""
    if isinstance(row, (tuple, list)) and len(row) == 3:
        return row[0], row[1], row[2]
    if hasattr(row, "calendar_link") and hasattr(row, "task") and hasattr(row, "contato"):
        return row.calendar_link, row.task, row.contato
    if isinstance(row, dict):
        return row["calendar_link"], row["task"], row["contato"]
    # fallback para testes com SimpleNamespace
    return getattr(row, "CalendarLink"), getattr(row, "ContactTask"), getattr(row, "Contato")


def sync_calendar_links_query(
    session,
    *,
    limit: int,
    status_filter: str = "pending_or_failed",
):
    try:
        from .models import CalendarLink, ContactTask, Contato  # type: ignore
    except ImportError:  # pragma: no cover
        from models import CalendarLink, ContactTask, Contato  # type: ignore

    query = (
        session.query(CalendarLink, ContactTask, Contato)
        .join(ContactTask, CalendarLink.task_id == ContactTask.id)
        .join(Contato, CalendarLink.contato_id == Contato.id)
        .filter(CalendarLink.provider == "google_calendar")
    )

    if status_filter == "pending_sync":
        query = query.filter(CalendarLink.sync_status == "pending_sync")
    elif status_filter == "failed_sync":
        query = query.filter(CalendarLink.sync_status == "failed_sync")
    elif status_filter == "all":
        pass
    else:
        query = query.filter(CalendarLink.sync_status.in_(["pending_sync", "failed_sync"]))

    return query.order_by(CalendarLink.created_at.asc()).limit(limit).all()


def sync_calendar_links(
    session,
    *,
    calendar_id: str | None = None,
    limit: int = 20,
    status_filter: str = "pending_or_failed",
    client: GoogleCalendarClient | None = None,
) -> dict[str, Any]:
    target_calendar_id = calendar_id or os.environ.get("GOOGLE_CALENDAR_ID", "primary")
    gc_client = client or build_google_calendar_client_from_env()
    rows = sync_calendar_links_query(session, limit=limit, status_filter=status_filter)

    synced = 0
    failed = 0
    skipped = 0
    details: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for row in rows:
        calendar_link, task, contato = _row_to_namespace(row)

        if getattr(task, "sync_calendar", False) is False:
            skipped += 1
            details.append(
                {
                    "calendar_link_id": str(calendar_link.id),
                    "task_id": str(task.id),
                    "status": "skipped",
                    "reason": "task.sync_calendar=false",
                }
            )
            continue

        if (getattr(task, "status", "") or "").lower() in {"cancelled", "canceled"}:
            calendar_link.sync_status = "failed_sync"
            calendar_link.sync_error = "task_cancelled"
            calendar_link.last_sync_at = now
            skipped += 1
            details.append(
                {
                    "calendar_link_id": str(calendar_link.id),
                    "task_id": str(task.id),
                    "status": "skipped",
                    "reason": "task cancelled",
                }
            )
            continue

        try:
            payload = build_google_event_payload(contato=contato, task=task)
            response = gc_client.upsert_event(
                calendar_id=target_calendar_id,
                event_payload=payload,
                event_id=calendar_link.calendar_event_id,
            )
            calendar_link.calendar_event_id = response.get("id") or calendar_link.calendar_event_id
            calendar_link.sync_status = "synced"
            calendar_link.last_sync_at = now
            calendar_link.sync_error = None
            synced += 1
            details.append(
                {
                    "calendar_link_id": str(calendar_link.id),
                    "task_id": str(task.id),
                    "status": "synced",
                    "calendar_event_id": calendar_link.calendar_event_id,
                }
            )
        except Exception as exc:
            calendar_link.sync_status = "failed_sync"
            calendar_link.sync_error = str(exc)[:1000]
            calendar_link.last_sync_at = now
            failed += 1
            details.append(
                {
                    "calendar_link_id": str(calendar_link.id),
                    "task_id": str(task.id),
                    "status": "failed_sync",
                    "error": str(exc),
                }
            )

    return {
        "calendar_id": target_calendar_id,
        "processed": len(rows),
        "synced": synced,
        "failed": failed,
        "skipped": skipped,
        "details": details,
    }
