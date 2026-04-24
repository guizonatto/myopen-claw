import pytest

from mcps.crm_mcp.readiness import (
    ReadinessInput,
    calculate_readiness,
    can_transition,
)


def test_divergence_penalty_is_capped_at_30() -> None:
    payload = ReadinessInput(
        has_whatsapp=True,
        has_email=True,
        has_phone=True,
        verified_signals_count=3,
        icp_type="A",
        pain_hypothesis="Perde vendas por demora",
        fresh_days=2,
        intent_signal=9,
        enrichment_confidence=0.40,
        divergence_whatsapp=True,
        divergence_email=True,
        divergence_company_or_cnpj=True,
        attempts_without_response=0,
        do_not_contact=False,
        has_best_contact_window=True,
    )

    result = calculate_readiness(payload)

    assert result.penalties["divergence"] == 30
    assert result.penalties["confidence"] == 18
    assert result.gate_passed is False


def test_three_attempts_without_response_forces_lost_pipeline() -> None:
    payload = ReadinessInput(
        has_whatsapp=True,
        has_email=False,
        has_phone=True,
        verified_signals_count=2,
        icp_type="B",
        pain_hypothesis="Sem previsibilidade",
        fresh_days=5,
        intent_signal=7,
        enrichment_confidence=0.8,
        divergence_whatsapp=False,
        divergence_email=False,
        divergence_company_or_cnpj=False,
        attempts_without_response=3,
        do_not_contact=False,
        has_best_contact_window=True,
    )

    result = calculate_readiness(payload)

    assert result.penalties["engagement"] == 15
    assert result.suggested_pipeline_status == "perdido"
    assert result.gate_passed is False


def test_do_not_contact_is_hard_block() -> None:
    payload = ReadinessInput(
        has_whatsapp=True,
        has_email=True,
        has_phone=False,
        verified_signals_count=3,
        icp_type="A",
        pain_hypothesis="Sem controle",
        fresh_days=1,
        intent_signal=10,
        enrichment_confidence=0.95,
        divergence_whatsapp=False,
        divergence_email=False,
        divergence_company_or_cnpj=False,
        attempts_without_response=0,
        do_not_contact=True,
        has_best_contact_window=True,
    )

    result = calculate_readiness(payload)

    assert result.hard_block_reason == "do_not_contact"
    assert result.gate_passed is False


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        ("ingested", "verified", True),
        ("verified", "contacted", False),
        ("approved", "contacted", True),
        ("follow_up", "approved", False),
    ],
)
def test_readiness_state_transitions(current: str, target: str, expected: bool) -> None:
    assert can_transition(current, target) is expected
