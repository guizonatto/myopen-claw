from __future__ import annotations

from dataclasses import dataclass


READINESS_STATES = {
    "ingested",
    "verified",
    "enriched",
    "qualified",
    "awaiting_approval",
    "approved",
    "contacted",
    "follow_up",
    "blocked",
}

READINESS_TRANSITIONS: dict[str, set[str]] = {
    "ingested": {"verified", "blocked"},
    "verified": {"enriched", "blocked"},
    "enriched": {"qualified", "blocked"},
    "qualified": {"awaiting_approval", "blocked"},
    "awaiting_approval": {"approved", "blocked"},
    "approved": {"contacted", "blocked"},
    "contacted": {"follow_up", "blocked"},
    "follow_up": {"blocked"},
    "blocked": set(),
}


def can_transition(current: str | None, target: str) -> bool:
    if target not in READINESS_STATES:
        return False
    if not current:
        return target in {"ingested", "verified", "blocked"}
    if current == target:
        return True
    return target in READINESS_TRANSITIONS.get(current, set())


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ReadinessInput:
    has_whatsapp: bool
    has_email: bool
    has_phone: bool
    verified_signals_count: int
    icp_type: str | None
    pain_hypothesis: str | None
    fresh_days: int | None
    intent_signal: int
    enrichment_confidence: float
    divergence_whatsapp: bool
    divergence_email: bool
    divergence_company_or_cnpj: bool
    attempts_without_response: int
    do_not_contact: bool
    has_best_contact_window: bool


@dataclass(frozen=True)
class ReadinessResult:
    positive_score: int
    penalty_score: int
    readiness_score: int
    positives: dict[str, int]
    penalties: dict[str, int]
    gate_passed: bool
    hard_block_reason: str | None
    suggested_pipeline_status: str | None


def _contactability_score(payload: ReadinessInput) -> int:
    score = 0
    if payload.has_whatsapp:
        score += 15
    if payload.has_email:
        score += 8
    if payload.has_phone:
        score += 5
    return _clamp(score, 0, 25)


def _verification_score(payload: ReadinessInput) -> int:
    return _clamp(payload.verified_signals_count * 10, 0, 20)


def _icp_fit_score(payload: ReadinessInput) -> int:
    value = (payload.icp_type or "").strip().lower()
    if value == "a":
        return 20
    if value == "b":
        return 14
    if value == "hesitante":
        return 8
    return 0


def _freshness_score(payload: ReadinessInput) -> int:
    if payload.fresh_days is None:
        return 0
    if payload.fresh_days <= 7:
        return 15
    if payload.fresh_days <= 14:
        return 10
    if payload.fresh_days <= 30:
        return 4
    return 0


def _pain_signal_score(payload: ReadinessInput) -> int:
    return 10 if (payload.pain_hypothesis or "").strip() else 0


def _intent_signal_score(payload: ReadinessInput) -> int:
    return _clamp(payload.intent_signal, 0, 10)


def _divergence_penalty(payload: ReadinessInput) -> int:
    penalty = 0
    if payload.divergence_whatsapp:
        penalty += 20
    if payload.divergence_email:
        penalty += 12
    if payload.divergence_company_or_cnpj:
        penalty += 10
    return _clamp(penalty, 0, 30)


def _confidence_penalty(payload: ReadinessInput) -> int:
    if payload.enrichment_confidence < 0.50:
        return 18
    if payload.enrichment_confidence < 0.65:
        return 10
    return 0


def _freshness_penalty(payload: ReadinessInput) -> int:
    if payload.fresh_days is None:
        return 25
    if payload.fresh_days > 30:
        return 25
    if payload.fresh_days >= 15:
        return 15
    if payload.fresh_days >= 8:
        return 8
    return 0


def _context_penalty(payload: ReadinessInput) -> int:
    penalty = 0
    if not (payload.pain_hypothesis or "").strip():
        penalty += 6
    if not (payload.icp_type or "").strip():
        penalty += 8
    if not payload.has_best_contact_window:
        penalty += 4
    return penalty


def _engagement_penalty(payload: ReadinessInput) -> tuple[int, str | None]:
    if payload.attempts_without_response >= 3:
        return 15, "perdido"
    if payload.attempts_without_response >= 2:
        return 8, None
    return 0, None


def calculate_readiness(payload: ReadinessInput) -> ReadinessResult:
    positives = {
        "contactability": _contactability_score(payload),
        "verification": _verification_score(payload),
        "icp_fit": _icp_fit_score(payload),
        "freshness": _freshness_score(payload),
        "pain_signal": _pain_signal_score(payload),
        "intent_signal": _intent_signal_score(payload),
    }
    positive_score = sum(positives.values())

    engagement_penalty, suggested_pipeline_status = _engagement_penalty(payload)
    penalties = {
        "divergence": _divergence_penalty(payload),
        "confidence": _confidence_penalty(payload),
        "freshness": _freshness_penalty(payload),
        "context": _context_penalty(payload),
        "engagement": engagement_penalty,
    }
    penalty_score = sum(penalties.values())
    readiness_score = _clamp(positive_score - penalty_score, 0, 100)

    hard_block_reason = None
    if payload.do_not_contact:
        hard_block_reason = "do_not_contact"
    elif not (payload.has_whatsapp or payload.has_email or payload.has_phone):
        hard_block_reason = "no_valid_channel"

    is_fresh_enough = payload.fresh_days is not None and payload.fresh_days <= 7
    gate_passed = (
        hard_block_reason is None
        and readiness_score >= 70
        and payload.verified_signals_count >= 2
        and is_fresh_enough
        and suggested_pipeline_status != "perdido"
    )

    return ReadinessResult(
        positive_score=positive_score,
        penalty_score=penalty_score,
        readiness_score=readiness_score,
        positives=positives,
        penalties=penalties,
        gate_passed=gate_passed,
        hard_block_reason=hard_block_reason,
        suggested_pipeline_status=suggested_pipeline_status,
    )
