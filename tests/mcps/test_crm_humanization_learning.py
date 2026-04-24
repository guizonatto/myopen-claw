from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mcps.crm_mcp.conversation_engine import build_personalized_draft
from mcps.crm_mcp.message_strategy import (
    compute_confidence,
    compute_outcome_score,
    compute_smoothed_score,
    record_strategy_outcome,
    resolve_sla_outcome,
    select_message_strategy,
    update_strategy_ranking,
)
from mcps.crm_mcp.models import MessageStrategyRanking


class _RankingQuery:
    def __init__(self, session):
        self._session = session

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._session.rankings.values())

    def first(self):
        if not self._session.rankings:
            return None
        return next(iter(self._session.rankings.values()))


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _StrategySession:
    def __init__(self):
        self.rankings: dict[str, MessageStrategyRanking] = {}
        self.outcomes = []

    def query(self, model):
        if model is MessageStrategyRanking:
            return _RankingQuery(self)
        return _EmptyQuery()

    def add(self, row):
        if isinstance(row, MessageStrategyRanking):
            key = getattr(row, "strategy_key", None)
            self.rankings[key] = row
        if getattr(row, "score_delta", None) is not None:
            self.outcomes.append(row)

    def flush(self):
        return None


def _contact(**overrides):
    base = {
        "nome": "Joao Silva",
        "empresa": "Condominio Alfa",
        "pipeline_status": "lead",
        "pain_hypothesis": "demora no follow-up e perda de oportunidade",
        "recent_signal": "vi aumento de demanda na regiao",
        "setor": "condominios",
        "tipo": None,
        "client_type": "condominio",
        "city": "sao_paulo",
        "region": "sudeste",
        "whatsapp": "+5511999990000",
        "telefone": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_whatsapp_short_message_stays_single_chunk():
    contato = _contact(
        pain_hypothesis="demora no atendimento",
        recent_signal="",
    )
    payload = build_personalized_draft(
        contato,
        channel="whatsapp",
        strategy={
            "strategy_key": "lead|condominio|sao_paulo|whatsapp|context_open_question",
            "message_archetype": "context_open_question",
            "template_hint": "abertura curta",
            "confidence": 0.2,
        },
    )

    assert payload["split_applied"] is False
    assert len(payload["messages"]) == 1
    assert len(payload["messages"][0]) <= 220


def test_whatsapp_long_message_splits_into_2_or_3_chunks():
    contato = _contact(
        pain_hypothesis="falta de previsibilidade no comercial, retrabalho diário e muitas mensagens sem resposta",
        recent_signal="site com campanhas novas e aumento de volume de contatos recebidos",
    )
    payload = build_personalized_draft(
        contato,
        channel="whatsapp",
        strategy={
            "strategy_key": "lead|condominio|sao_paulo|whatsapp|pain_mirror",
            "message_archetype": "pain_mirror",
            "template_hint": "contexto real sem soar robótico",
            "confidence": 0.2,
        },
    )

    assert payload["split_applied"] is True
    assert 2 <= len(payload["messages"]) <= 3
    assert all(len(message) <= 220 for message in payload["messages"])
    assert payload["checks"]["cta_only_last_chunk"] is True
    assert payload["checks"]["anti_text_wall"] is True


def test_strategy_retrieval_precedence(monkeypatch):
    session = _StrategySession()
    monkeypatch.setattr("mcps.crm_mcp.message_strategy.random.random", lambda: 1.0)

    exact = select_message_strategy(session, _contact(city="sao_paulo", client_type="condominio"), channel="whatsapp")
    wildcard_city = select_message_strategy(session, _contact(city="campinas", client_type="condominio"), channel="whatsapp")
    wildcard_city_channel = select_message_strategy(session, _contact(city="campinas", client_type="condominio"), channel="email")
    stage_global = select_message_strategy(session, _contact(city="campinas", client_type="cliente_novo"), channel="email")

    assert exact["retrieval_level"] == "exact"
    assert wildcard_city["retrieval_level"] == "wildcard_city"
    assert wildcard_city_channel["retrieval_level"] == "wildcard_city_channel"
    assert stage_global["retrieval_level"] == "stage_global"


@pytest.mark.parametrize(
    ("outcome", "elapsed_hours", "expected_outcome", "expected_points"),
    [
        ("reply", None, "reply", 3.0),
        ("meeting_scheduled", None, "meeting_scheduled", 6.0),
        ("stage_advance", None, "stage_advance", 10.0),
        ("no_reply", 25.0, "no_reply_first_window", -2.0),
        ("no_reply", 52.0, "no_reply_second_window", -4.0),
        ("no_interest", None, "no_interest", -10.0),
    ],
)
def test_weighted_outcome_and_sla_windows(outcome, elapsed_hours, expected_outcome, expected_points):
    normalized = resolve_sla_outcome(outcome, elapsed_hours=elapsed_hours, sla_hours=24)
    stage_hops = 2 if expected_outcome == "stage_advance" else 0
    points = compute_outcome_score(normalized, stage_hops=stage_hops)

    assert normalized == expected_outcome
    assert points == expected_points


def test_bayesian_smoothing_confidence_and_low_confidence():
    session = _StrategySession()
    strategy_key = "lead|condominio|sao_paulo|whatsapp|context_open_question"

    for _ in range(5):
        row = update_strategy_ranking(
            session,
            stage="lead",
            client_type="condominio",
            city="sao_paulo",
            region="sudeste",
            channel="whatsapp",
            message_archetype="context_open_question",
            strategy_key=strategy_key,
            score_delta=3.0,
            outcome_at=datetime.now(tz=timezone.utc),
        )

    expected_smoothed = compute_smoothed_score(
        total_outcome_points=15.0,
        attempts=5,
        prior_mean=0.0,
        prior_weight=5.0,
    )
    expected_confidence = compute_confidence(attempts=5, prior_weight=5.0)

    assert row.attempts == 5
    assert row.total_outcome_points == 15.0
    assert row.smoothed_score == pytest.approx(expected_smoothed, rel=1e-9)
    assert row.confidence == pytest.approx(expected_confidence, rel=1e-9)
    assert row.low_confidence is False


def test_integration_record_outcome_updates_next_selection(monkeypatch):
    session = _StrategySession()
    contato = _contact(city="sao_paulo", region="sudeste", client_type="condominio")
    monkeypatch.setattr("mcps.crm_mcp.message_strategy.random.random", lambda: 1.0)

    before = select_message_strategy(session, contato, channel="whatsapp")
    result = record_strategy_outcome(
        session,
        contato_id="contact-1",
        interaction_id="interaction-1",
        stage=before["stage"],
        client_type=before["client_type"],
        city=before["city"],
        region=before["region"],
        channel=before["channel"],
        message_archetype=before["message_archetype"],
        strategy_key=before["strategy_key"],
        outcome="reply",
        stage_hops=0,
        metadata={"source": "unit_test"},
    )
    after = select_message_strategy(session, contato, channel="whatsapp")

    assert result["ranking"]["attempts"] == 1
    assert result["ranking"]["total_outcome_points"] == 3.0
    assert after["strategy_key"] == before["strategy_key"]
    assert after["confidence"] > 0.0
