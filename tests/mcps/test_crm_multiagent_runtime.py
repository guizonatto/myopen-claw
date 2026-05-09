from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from mcps.crm_mcp import contatos
from mcps.crm_mcp.models import Contato


def test_route_conversation_turn_detects_no_interest():
    result = contatos.route_conversation_turn({"text": "não tenho interesse, pode remover meu contato"})

    assert result["intent"] == "no_interest"
    assert result["specialist"] == "zind-crm-handover"
    assert "block_and_stop" in result["policy_flags"]


def test_route_conversation_turn_detects_proactive_event():
    result = contatos.route_conversation_turn({"text": "", "system_event": "timeout_24h"})

    assert result["intent"] == "proactive_follow_up"
    assert result["specialist"] == "zind-crm-cold-contact"
    assert "soft_ping" in result["policy_flags"]


def test_transcribe_incoming_audio_with_hint():
    result = contatos.transcribe_incoming_audio(
        message_id="msg-1",
        media_ref="https://audio.invalid/file.ogg",
        transcript_hint="Podemos conversar amanhã?",
    )

    assert result["provider"] == "hint"
    assert result["confidence"] == 0.95
    assert "amanhã" in result["text"]


def test_transcribe_incoming_audio_text_ref():
    result = contatos.transcribe_incoming_audio(
        message_id="msg-2",
        media_ref="text:Tenho interesse, pode me mandar mais detalhes?",
    )

    assert result["provider"] == "text_ref"
    assert result["confidence"] > 0.0
    assert "interesse" in result["text"]


class _ContatoQuery:
    def __init__(self, contatos_rows):
        self._rows = contatos_rows

    def filter(self, *args, **kwargs):
        return self

    def limit(self, _n):
        return self

    def all(self):
        return self._rows


class _SessionFake:
    def __init__(self, contatos_rows):
        self._contatos_rows = contatos_rows
        self.added = []

    def query(self, model):
        if model is Contato:
            return _ContatoQuery(self._contatos_rows)
        raise AssertionError(f"Unexpected model in fake query: {model}")

    def add(self, row):
        self.added.append(row)


def test_evaluate_dormant_leads_triggers_timeout(monkeypatch):
    contato_row = SimpleNamespace(
        id=str(uuid4()),
        ativo=True,
        do_not_contact=False,
        pipeline_status="qualificado",
    )
    session = _SessionFake([contato_row])

    @contextmanager
    def _fake_get_session():
        yield session

    now = datetime.now(tz=timezone.utc)
    monkeypatch.setattr(contatos, "get_session", _fake_get_session)
    monkeypatch.setattr(contatos, "_utcnow", lambda: now)
    monkeypatch.setattr(contatos, "_resolve_last_outbound_at", lambda *_args, **_kwargs: now - timedelta(hours=50))
    monkeypatch.setattr(contatos, "_resolve_last_inbound_interaction", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(contatos, "_resolve_last_internal_timeout", lambda *_args, **_kwargs: False)

    result = contatos.evaluate_dormant_leads(limit=10)

    assert result["evaluated"] == 1
    assert result["triggered"] == 1
    assert result["events"][0]["event_type"] == "timeout_48h"
    assert session.added, "Expected internal event interaction to be added to session"


def test_evaluate_dormant_leads_pauses_after_72h(monkeypatch):
    contato_row = SimpleNamespace(
        id=str(uuid4()),
        ativo=True,
        do_not_contact=False,
        pipeline_status="qualificado",
        updated_at=None,
    )
    session = _SessionFake([contato_row])

    @contextmanager
    def _fake_get_session():
        yield session

    now = datetime.now(tz=timezone.utc)
    monkeypatch.setattr(contatos, "get_session", _fake_get_session)
    monkeypatch.setattr(contatos, "_utcnow", lambda: now)
    monkeypatch.setattr(contatos, "_resolve_last_outbound_at", lambda *_args, **_kwargs: now - timedelta(hours=80))
    monkeypatch.setattr(contatos, "_resolve_last_inbound_interaction", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(contatos, "_resolve_last_internal_timeout", lambda *_args, **_kwargs: False)

    result = contatos.evaluate_dormant_leads(limit=10)

    assert result["triggered"] == 1
    assert result["events"][0]["event_type"] == "timeout_72h"
    assert result["paused_contacts"] == 1
    assert result["review_tasks_created"] == 1
    assert contato_row.pipeline_status == "follow_up_pause"
    assert any(getattr(item, "objective", "").startswith("Revisar lead pausado") for item in session.added)
