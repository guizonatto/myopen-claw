import json
from datetime import datetime, timezone
from types import SimpleNamespace

from mcps.crm_mcp.calendar_sync import (
    GoogleCalendarClient,
    _load_service_account_info,
    build_google_event_payload,
)


def test_load_service_account_info_from_json_env(monkeypatch):
    info = {
        "type": "service_account",
        "client_email": "svc@test.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nABC\\n-----END PRIVATE KEY-----\\n",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps(info))
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)

    loaded = _load_service_account_info()

    assert loaded["type"] == "service_account"
    assert loaded["client_email"] == info["client_email"]


def test_google_calendar_client_post_for_new_event():
    calls = []

    def fake_transport(method, url, payload):
        calls.append((method, url, payload))
        return {"id": "evt-new-1"}

    client = GoogleCalendarClient("token", transport=fake_transport)
    result = client.upsert_event("primary", {"summary": "Teste"})

    assert result["id"] == "evt-new-1"
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/calendars/primary/events")


def test_google_calendar_client_patch_for_existing_event():
    calls = []

    def fake_transport(method, url, payload):
        calls.append((method, url, payload))
        return {"id": "evt-old-1"}

    client = GoogleCalendarClient("token", transport=fake_transport)
    result = client.upsert_event("primary", {"summary": "Teste"}, event_id="evt-old-1")

    assert result["id"] == "evt-old-1"
    assert calls[0][0] == "PATCH"
    assert calls[0][1].endswith("/calendars/primary/events/evt-old-1")


def test_build_google_event_payload_has_reminder_and_metadata():
    contato = SimpleNamespace(
        id="contact-1",
        nome="Joao Silva",
        empresa="Condominio XPTO",
        whatsapp="+5511999990000",
        email="joao@xpto.com",
    )
    task = SimpleNamespace(
        id="task-1",
        due_at=datetime(2026, 4, 25, 14, 0, tzinfo=timezone.utc),
        reminder_at=datetime(2026, 4, 25, 13, 30, tzinfo=timezone.utc),
        channel="whatsapp",
        objective="Confirmar reuniao de 15 minutos",
        owner="time_outbound",
    )

    payload = build_google_event_payload(contato=contato, task=task, default_timezone="America/Sao_Paulo")

    assert payload["summary"].startswith("CRM Follow-up:")
    assert payload["start"]["timeZone"] == "America/Sao_Paulo"
    assert payload["extendedProperties"]["private"]["crm_task_id"] == "task-1"
    assert payload["reminders"]["overrides"][0]["minutes"] == 30
