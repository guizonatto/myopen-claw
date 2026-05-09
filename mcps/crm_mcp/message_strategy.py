from __future__ import annotations

import json
import random
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func

try:
    from .models import MessageStrategyOutcome, MessageStrategyRanking
except ImportError:  # pragma: no cover
    from models import MessageStrategyOutcome, MessageStrategyRanking


DEFAULT_EPSILON = 0.15
DEFAULT_PRIOR_MEAN = 0.0
DEFAULT_PRIOR_WEIGHT = 5.0
DEFAULT_LOW_CONFIDENCE_ATTEMPTS = 5
DISCORD_MESSAGE_LIMIT = 1900
WILDCARD = "*"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _library_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "crm" / "library"


def _load_json(name: str) -> dict[str, Any]:
    path = _library_dir() / name
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _slug(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or fallback


def _clean_channel(channel: str | None) -> str:
    return _slug(channel or "whatsapp", "whatsapp")


def _infer_region_from_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    if digits.startswith("55"):
        digits = digits[2:]
    if len(digits) < 10:
        return None
    try:
        ddd = int(digits[:2])
    except ValueError:
        return None

    if ddd in {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38}:
        return "sudeste"
    if ddd in {41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55}:
        return "sul"
    if ddd in {61, 62, 64, 63, 65, 66, 67, 68, 69}:
        return "centro_oeste"
    if ddd in {71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89}:
        return "nordeste"
    if ddd in {91, 92, 93, 94, 95, 96, 97, 98, 99}:
        return "norte"
    return None


def _infer_city_from_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    if digits.startswith("55"):
        digits = digits[2:]
    if len(digits) < 10:
        return None
    try:
        ddd = int(digits[:2])
    except ValueError:
        return None

    city_by_ddd = {
        11: "sao_paulo",
        21: "rio_de_janeiro",
        31: "belo_horizonte",
        41: "curitiba",
        51: "porto_alegre",
        61: "brasilia",
        71: "salvador",
        81: "recife",
        85: "fortaleza",
        91: "belem",
    }
    return city_by_ddd.get(ddd)


def _infer_client_type(contato: Any) -> str:
    if getattr(contato, "tipo", None):
        return _slug(contato.tipo, "general")
    setor = (getattr(contato, "setor", None) or "").strip().lower()
    if "condom" in setor:
        return "condominio"
    if "imobili" in setor:
        return "imobiliario"
    if "saude" in setor:
        return "saude"
    if setor:
        return _slug(setor, "general")
    return "general"


def resolve_contact_dimensions(contato: Any, channel: str, *, stage_override: str | None = None) -> dict[str, Any]:
    stage = _slug(stage_override or getattr(contato, "pipeline_status", None) or "lead", "lead")

    explicit_city = (getattr(contato, "city", None) or "").strip()
    explicit_client_type = (getattr(contato, "client_type", None) or "").strip()
    explicit_region = (getattr(contato, "region", None) or "").strip()

    inferred_city = not bool(explicit_city)
    inferred_client_type = not bool(explicit_client_type)
    inferred_region = not bool(explicit_region)

    city = _slug(explicit_city, "") if explicit_city else (
        _infer_city_from_phone(getattr(contato, "whatsapp", None))
        or _infer_city_from_phone(getattr(contato, "telefone", None))
        or "unknown"
    )
    client_type = _slug(explicit_client_type, "") if explicit_client_type else _infer_client_type(contato)
    region = _slug(explicit_region, "") if explicit_region else (
        _infer_region_from_phone(getattr(contato, "whatsapp", None))
        or _infer_region_from_phone(getattr(contato, "telefone", None))
        or "unknown"
    )

    return {
        "stage": stage,
        "city": city or "unknown",
        "client_type": client_type or "general",
        "region": region or "unknown",
        "channel": _clean_channel(channel),
        "inferred_city": inferred_city,
        "inferred_client_type": inferred_client_type,
        "inferred_region": inferred_region,
    }


def apply_inference_to_contact(contato: Any, dimensions: dict[str, Any]) -> None:
    if dimensions.get("inferred_city"):
        contato.city = dimensions["city"]
    contato.inferred_city = bool(dimensions.get("inferred_city"))

    if dimensions.get("inferred_region"):
        contato.region = dimensions["region"]
    contato.inferred_region = bool(dimensions.get("inferred_region"))

    if dimensions.get("inferred_client_type"):
        contato.client_type = dimensions["client_type"]
    contato.inferred_client_type = bool(dimensions.get("inferred_client_type"))


def _learning_config(seed_payload: dict[str, Any]) -> dict[str, float]:
    prior = seed_payload.get("prior", {})
    return {
        "epsilon": float(prior.get("epsilon", DEFAULT_EPSILON)),
        "prior_mean": float(prior.get("mean", DEFAULT_PRIOR_MEAN)),
        "prior_weight": float(prior.get("weight", DEFAULT_PRIOR_WEIGHT)),
        "low_confidence_attempts": int(prior.get("low_confidence_attempts", DEFAULT_LOW_CONFIDENCE_ATTEMPTS)),
    }


def compute_smoothed_score(*, total_outcome_points: float, attempts: int, prior_mean: float, prior_weight: float) -> float:
    return (prior_weight * prior_mean + total_outcome_points) / (prior_weight + max(attempts, 0))


def compute_confidence(*, attempts: int, prior_weight: float) -> float:
    attempts = max(attempts, 0)
    return attempts / (attempts + prior_weight)


def build_strategy_key(stage: str, client_type: str, city: str, channel: str, message_archetype: str) -> str:
    return "|".join(
        [
            _slug(stage, "lead"),
            _slug(client_type, "general"),
            _slug(city, "unknown"),
            _slug(channel, "whatsapp"),
            _slug(message_archetype, "stage_global_default"),
        ]
    )


def _seed_strategies(seed_payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = seed_payload.get("strategies", [])
    if not isinstance(data, list):
        return []

    output: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        stage = _slug(item.get("stage", "lead"), "lead")
        client_type = item.get("client_type", WILDCARD)
        city = item.get("city", item.get("region", WILDCARD))
        region = item.get("region", WILDCARD)
        channel = item.get("channel", WILDCARD)
        message_archetype = _slug(item.get("message_archetype"), "stage_global_default")

        normalized = dict(item)
        normalized["stage"] = stage
        normalized["city"] = WILDCARD if city == WILDCARD else _slug(city, "unknown")
        normalized["client_type"] = WILDCARD if client_type == WILDCARD else _slug(client_type, "general")
        normalized["region"] = WILDCARD if region == WILDCARD else _slug(region, "unknown")
        normalized["channel"] = WILDCARD if channel == WILDCARD else _slug(channel, "whatsapp")
        normalized["message_archetype"] = message_archetype
        normalized["strategy_key"] = build_strategy_key(
            stage=stage,
            client_type=normalized["client_type"] if normalized["client_type"] != WILDCARD else "any",
            city=normalized["city"] if normalized["city"] != WILDCARD else "any",
            channel=normalized["channel"] if normalized["channel"] != WILDCARD else "any",
            message_archetype=message_archetype,
        )
        output.append(normalized)
    return output


def _filter_strategies(
    strategies: Iterable[dict[str, Any]],
    *,
    stage: str,
    client_type: str,
    city: str,
    channel: str,
) -> list[dict[str, Any]]:
    return [
        strategy
        for strategy in strategies
        if strategy.get("stage") == stage
        and strategy.get("client_type") == client_type
        and strategy.get("city") == city
        and strategy.get("channel") == channel
    ]


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2}


def _semantic_score(strategy: dict[str, Any], query_tokens: set[str]) -> float:
    tags = strategy.get("tags") or []
    joined = " ".join(
        [
            strategy.get("stage", ""),
            strategy.get("client_type", ""),
            strategy.get("city", ""),
            strategy.get("region", ""),
            strategy.get("channel", ""),
            strategy.get("message_archetype", ""),
            strategy.get("template_hint", ""),
            " ".join(tags if isinstance(tags, list) else []),
        ]
    )
    strategy_tokens = _tokenize(joined)
    if not strategy_tokens:
        return 0.0
    overlap = query_tokens & strategy_tokens
    return len(overlap) / max(len(query_tokens), 1)


def _retrieval_candidates(
    strategies: list[dict[str, Any]],
    *,
    stage: str,
    client_type: str,
    city: str,
    channel: str,
) -> tuple[str, list[dict[str, Any]]]:
    exact = _filter_strategies(
        strategies,
        stage=stage,
        client_type=client_type,
        city=city,
        channel=channel,
    )
    if exact:
        return "exact", exact

    wildcard_city = _filter_strategies(
        strategies,
        stage=stage,
        client_type=client_type,
        city=WILDCARD,
        channel=channel,
    )
    if wildcard_city:
        return "wildcard_city", wildcard_city

    wildcard_city_channel = _filter_strategies(
        strategies,
        stage=stage,
        client_type=client_type,
        city=WILDCARD,
        channel=WILDCARD,
    )
    if wildcard_city_channel:
        return "wildcard_city_channel", wildcard_city_channel

    stage_global = _filter_strategies(
        strategies,
        stage=stage,
        client_type=WILDCARD,
        city=WILDCARD,
        channel=WILDCARD,
    )
    if stage_global:
        return "stage_global", stage_global

    query_tokens = _tokenize(" ".join([stage, client_type, city, channel]))
    ranked = sorted(
        (
            (strategy, _semantic_score(strategy, query_tokens))
            for strategy in strategies
            if strategy.get("stage") in {stage, WILDCARD}
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    semantic = [item[0] for item in ranked if item[1] > 0]
    if semantic:
        return "semantic_fallback", semantic[:5]

    return "semantic_fallback", []


def _candidate_key(strategy: dict[str, Any], dimensions: dict[str, Any]) -> str:
    return build_strategy_key(
        stage=dimensions["stage"],
        client_type=dimensions["client_type"],
        city=dimensions["city"],
        channel=dimensions["channel"],
        message_archetype=strategy["message_archetype"],
    )


def _ranking_defaults(config: dict[str, float]) -> dict[str, Any]:
    return {
        "attempts": 0,
        "smoothed_score": config["prior_mean"],
        "confidence": 0.0,
        "low_confidence": True,
    }


def select_message_strategy(
    session,
    contato: Any,
    *,
    channel: str,
    stage_override: str | None = None,
    archetype_hint: str | None = None,
) -> dict[str, Any]:
    seed_payload = _load_json("message_strategy_seed.json")
    config = _learning_config(seed_payload)
    dimensions = resolve_contact_dimensions(contato, channel, stage_override=stage_override)
    strategies = _seed_strategies(seed_payload)

    retrieval_level, candidates = _retrieval_candidates(
        strategies,
        stage=dimensions["stage"],
        client_type=dimensions["client_type"],
        city=dimensions["city"],
        channel=dimensions["channel"],
    )

    if archetype_hint:
        hint_slug = _slug(archetype_hint, "")
        hinted = [c for c in candidates if c.get("message_archetype") == hint_slug]
        if hinted:
            candidates = hinted
            retrieval_level = f"{retrieval_level}_hint"
        elif hint_slug:
            archetype_candidates = [
                strategy
                for strategy in strategies
                if strategy.get("stage") == dimensions["stage"]
                and strategy.get("message_archetype") == hint_slug
                and strategy.get("client_type") in {dimensions["client_type"], WILDCARD}
                and strategy.get("city") in {dimensions["city"], WILDCARD}
                and strategy.get("channel") in {dimensions["channel"], WILDCARD}
            ]
            if archetype_candidates:
                def _specificity_score(item: dict[str, Any]) -> tuple[int, int, int]:
                    return (
                        1 if item.get("client_type") == dimensions["client_type"] else 0,
                        1 if item.get("city") == dimensions["city"] else 0,
                        1 if item.get("channel") == dimensions["channel"] else 0,
                    )

                archetype_candidates.sort(key=_specificity_score, reverse=True)
                candidates = archetype_candidates
                retrieval_level = "archetype_override"

    if not candidates:
        fallback_archetype = _slug(archetype_hint, "stage_global_default")
        strategy_key = build_strategy_key(
            dimensions["stage"],
            dimensions["client_type"],
            dimensions["city"],
            dimensions["channel"],
            fallback_archetype,
        )
        return {
            **dimensions,
            "strategy_key": strategy_key,
            "message_archetype": fallback_archetype,
            "template_hint": "mensagem curta e contextual com CTA no final",
            "tags": [],
            "retrieval_level": retrieval_level,
            "attempts": 0,
            "smoothed_score": config["prior_mean"],
            "confidence": 0.0,
            "low_confidence": True,
            "exploration_applied": False,
            "epsilon": config["epsilon"],
        }

    keys = [_candidate_key(candidate, dimensions) for candidate in candidates]
    ranking_rows = (
        session.query(MessageStrategyRanking)
        .filter(MessageStrategyRanking.strategy_key.in_(keys))
        .all()
    )
    ranking_by_key = {row.strategy_key: row for row in ranking_rows}

    ranked_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        effective_key = _candidate_key(candidate, dimensions)
        row = ranking_by_key.get(effective_key)
        baseline = _ranking_defaults(config)
        ranked_candidates.append(
            {
                "candidate": candidate,
                "strategy_key": effective_key,
                "attempts": int(getattr(row, "attempts", baseline["attempts"])),
                "smoothed_score": float(getattr(row, "smoothed_score", baseline["smoothed_score"])),
                "confidence": float(getattr(row, "confidence", baseline["confidence"])),
                "low_confidence": bool(getattr(row, "low_confidence", baseline["low_confidence"])),
            }
        )

    ranked_candidates.sort(key=lambda item: (item["smoothed_score"], item["attempts"]), reverse=True)
    exploration_applied = False
    if len(ranked_candidates) > 1 and random.random() < config["epsilon"]:
        exploration_applied = True
        pool = ranked_candidates[: min(3, len(ranked_candidates))]
        selected = random.choice(pool)
    else:
        selected = ranked_candidates[0]

    candidate = selected["candidate"]
    return {
        **dimensions,
        "strategy_key": selected["strategy_key"],
        "message_archetype": candidate["message_archetype"],
        "template_hint": candidate.get("template_hint", ""),
        "tags": candidate.get("tags", []),
        "retrieval_level": retrieval_level,
        "attempts": selected["attempts"],
        "smoothed_score": selected["smoothed_score"],
        "confidence": selected["confidence"],
        "low_confidence": selected["low_confidence"],
        "exploration_applied": exploration_applied,
        "epsilon": config["epsilon"],
    }


def compute_outcome_score(outcome: str, *, stage_hops: int = 0) -> float:
    normalized = _slug(outcome, "unknown")
    if normalized == "reply":
        return 3.0
    if normalized == "stage_advance":
        return 5.0 * max(stage_hops, 1)
    if normalized == "meeting_scheduled":
        return 6.0
    if normalized == "no_reply_first_window":
        return -2.0
    if normalized == "no_reply_second_window":
        return -4.0
    if normalized in {"no_interest", "explicit_no_interest"}:
        return -10.0
    return 0.0


def resolve_sla_outcome(outcome: str, *, elapsed_hours: float | None, sla_hours: int) -> str:
    normalized = _slug(outcome, "unknown")
    if normalized != "no_reply":
        return normalized
    if elapsed_hours is None:
        return "no_reply_first_window"
    if elapsed_hours >= (2 * max(sla_hours, 1)):
        return "no_reply_second_window"
    return "no_reply_first_window"


def update_strategy_ranking(
    session,
    *,
    stage: str,
    client_type: str,
    city: str,
    region: str,
    channel: str,
    message_archetype: str,
    strategy_key: str,
    score_delta: float,
    outcome_at: datetime,
) -> MessageStrategyRanking:
    seed_payload = _load_json("message_strategy_seed.json")
    config = _learning_config(seed_payload)
    ranking = session.query(MessageStrategyRanking).filter(MessageStrategyRanking.strategy_key == strategy_key).first()
    if not ranking:
        ranking = MessageStrategyRanking(
            stage=stage,
            client_type=client_type,
            city=city,
            region=region,
            channel=channel,
            message_archetype=message_archetype,
            strategy_key=strategy_key,
            attempts=0,
            total_outcome_points=0.0,
            smoothed_score=config["prior_mean"],
            confidence=0.0,
            low_confidence=True,
        )
        session.add(ranking)
        session.flush()

    attempts = int(ranking.attempts or 0) + 1
    total_points = float(ranking.total_outcome_points or 0.0) + float(score_delta)
    prior_weight = config["prior_weight"]
    prior_mean = config["prior_mean"]
    smoothed = compute_smoothed_score(
        total_outcome_points=total_points,
        attempts=attempts,
        prior_mean=prior_mean,
        prior_weight=prior_weight,
    )
    confidence = compute_confidence(attempts=attempts, prior_weight=prior_weight)

    ranking.attempts = attempts
    ranking.total_outcome_points = total_points
    ranking.smoothed_score = smoothed
    ranking.confidence = confidence
    ranking.low_confidence = attempts < config["low_confidence_attempts"]
    ranking.last_outcome_at = outcome_at
    ranking.updated_at = outcome_at
    return ranking


def record_strategy_outcome(
    session,
    *,
    contato_id: str,
    interaction_id: str | None,
    stage: str,
    client_type: str,
    city: str,
    region: str,
    channel: str,
    message_archetype: str,
    strategy_key: str,
    outcome: str,
    stage_hops: int = 0,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_outcome = _slug(outcome, "unknown")
    score_delta = compute_outcome_score(normalized_outcome, stage_hops=stage_hops)
    now = _utcnow()

    outcome_row = MessageStrategyOutcome(
        contato_id=contato_id,
        interaction_id=interaction_id,
        stage=_slug(stage, "lead"),
        client_type=_slug(client_type, "general"),
        city=_slug(city, "unknown"),
        region=_slug(region, "unknown"),
        channel=_slug(channel, "whatsapp"),
        message_archetype=_slug(message_archetype, "stage_global_default"),
        strategy_key=strategy_key,
        outcome=normalized_outcome,
        stage_hops=max(stage_hops, 0),
        score_delta=score_delta,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    session.add(outcome_row)

    ranking_row = update_strategy_ranking(
        session,
        stage=outcome_row.stage,
        client_type=outcome_row.client_type,
        city=outcome_row.city,
        region=outcome_row.region,
        channel=outcome_row.channel,
        message_archetype=outcome_row.message_archetype,
        strategy_key=strategy_key,
        score_delta=score_delta,
        outcome_at=now,
    )
    session.flush()

    return {
        "outcome": outcome_row.to_dict(),
        "ranking": ranking_row.to_dict(),
    }


def split_discord_content(content: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    if len(content) <= limit:
        return [content]

    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0
    for line in content.splitlines():
        line_length = len(line) + (1 if current_lines else 0)
        if current_lines and current_length + line_length > limit:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_length = len(line)
            continue

        if len(line) > limit:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_length = 0
            for start in range(0, len(line), limit):
                chunks.append(line[start : start + limit])
            continue

        current_lines.append(line)
        current_length += line_length

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks or [content[:limit]]


def build_daily_improvement_snapshot(session, *, top_n: int = 5) -> dict[str, Any]:
    ranking_rows = (
        session.query(MessageStrategyRanking)
        .filter(MessageStrategyRanking.attempts > 0)
        .order_by(MessageStrategyRanking.smoothed_score.desc(), MessageStrategyRanking.attempts.desc())
        .all()
    )
    top_rows = ranking_rows[:top_n]
    bottom_rows = list(reversed(ranking_rows[-top_n:])) if ranking_rows else []

    grouped = (
        session.query(
            MessageStrategyRanking.stage,
            MessageStrategyRanking.client_type,
            MessageStrategyRanking.city,
            MessageStrategyRanking.region,
            func.avg(MessageStrategyRanking.smoothed_score).label("avg_score"),
            func.sum(MessageStrategyRanking.attempts).label("attempts"),
        )
        .filter(MessageStrategyRanking.attempts > 0)
        .group_by(
            MessageStrategyRanking.stage,
            MessageStrategyRanking.client_type,
            MessageStrategyRanking.city,
            MessageStrategyRanking.region,
        )
        .all()
    )
    grouped_sorted = sorted(
        grouped,
        key=lambda item: (float(item.avg_score or 0.0), int(item.attempts or 0)),
        reverse=True,
    )
    winners = grouped_sorted[:top_n]
    losers = list(reversed(grouped_sorted[-top_n:])) if grouped_sorted else []

    return {
        "top_strategies": [row.to_dict() for row in top_rows],
        "bottom_strategies": [row.to_dict() for row in bottom_rows],
        "winners": [
            {
                "stage": item.stage,
                "client_type": item.client_type,
                "city": item.city,
                "region": item.region,
                "avg_score": float(item.avg_score or 0.0),
                "attempts": int(item.attempts or 0),
            }
            for item in winners
        ],
        "losers": [
            {
                "stage": item.stage,
                "client_type": item.client_type,
                "city": item.city,
                "region": item.region,
                "avg_score": float(item.avg_score or 0.0),
                "attempts": int(item.attempts or 0),
            }
            for item in losers
        ],
    }


def render_daily_improvement_report(snapshot: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("Sales Bot Improvement Report")
    lines.append("")
    lines.append("Top 5 strategies")
    for index, item in enumerate(snapshot.get("top_strategies", []), start=1):
        lines.append(
            (
                f"{index}. {item['strategy_key']} | score={item['smoothed_score']:.2f} "
                f"| attempts={item['attempts']} | confidence={item['confidence']:.2f}"
            )
        )
    if not snapshot.get("top_strategies"):
        lines.append("1. Sem dados suficientes.")

    lines.append("")
    lines.append("Bottom 5 strategies")
    for index, item in enumerate(snapshot.get("bottom_strategies", []), start=1):
        lines.append(
            (
                f"{index}. {item['strategy_key']} | score={item['smoothed_score']:.2f} "
                f"| attempts={item['attempts']} | confidence={item['confidence']:.2f}"
            )
        )
    if not snapshot.get("bottom_strategies"):
        lines.append("1. Sem dados suficientes.")

    lines.append("")
    lines.append("Winners by stage/client_type/city")
    for index, item in enumerate(snapshot.get("winners", []), start=1):
        lines.append(
            f"{index}. {item['stage']} | {item['client_type']} | {item['city']} | avg={item['avg_score']:.2f} | n={item['attempts']}"
        )
    if not snapshot.get("winners"):
        lines.append("1. Sem dados suficientes.")

    lines.append("")
    lines.append("Losers by stage/client_type/city")
    for index, item in enumerate(snapshot.get("losers", []), start=1):
        lines.append(
            f"{index}. {item['stage']} | {item['client_type']} | {item['city']} | avg={item['avg_score']:.2f} | n={item['attempts']}"
        )
    if not snapshot.get("losers"):
        lines.append("1. Sem dados suficientes.")

    lines.append("")
    lines.append("Tuning suggestions")
    if snapshot.get("bottom_strategies"):
        for item in snapshot["bottom_strategies"][:3]:
            lines.append(
                (
                    f"- Reduzir frequência de `{item['message_archetype']}` em {item['stage']}/"
                    f"{item['client_type']}/{item.get('city', 'unknown')} e testar variação alternativa."
                )
            )
    else:
        lines.append("- Aumentar base de dados para liberar tuning estatístico.")

    return "\n".join(lines).strip()
