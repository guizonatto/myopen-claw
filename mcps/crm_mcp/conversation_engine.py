from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _library_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "crm" / "library"


def _load_json(name: str) -> dict[str, Any]:
    path = _library_dir() / name
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _pick_stage_playbook(pipeline_status: str | None) -> dict[str, str]:
    stage_playbook = _load_json("stage_playbook.json")
    stage = (pipeline_status or "lead").strip().lower()
    return stage_playbook.get(stage, stage_playbook["lead"])


def _resolve_pain_hint(contato: Any) -> str:
    if getattr(contato, "pain_hypothesis", None):
        return str(contato.pain_hypothesis).strip()
    setor = (getattr(contato, "setor", None) or "").strip()
    if setor:
        return f"ganhar previsibilidade no setor de {setor}"
    return "reduzir retrabalho operacional no dia a dia"


def _resolve_first_name(contato: Any) -> str:
    nome = (getattr(contato, "nome", None) or "pessoal").strip()
    return nome.split()[0] if nome else "pessoal"


def _normalize_spaces(value: str) -> str:
    return " ".join(value.split()).strip()


def _clip(value: str, limit: int) -> str:
    value = _normalize_spaces(value)
    if len(value) <= limit:
        return value
    return value[: max(limit - 3, 1)].rstrip() + "..."


def _build_message_parts(
    *,
    first_name: str,
    signal_text: str,
    pain: str,
    company: str,
    objective: str,
    cta: str,
    template_hint: str,
    archetype: str,
) -> tuple[str, str, str]:
    archetype = (archetype or "").strip().lower()
    if archetype == "human_direct_probe_3step":
        return (
            _normalize_spaces(f"Ola {first_name}, tudo bem?"),
            "Vi seu contato no Google.",
            "Voce ainda atende como sindico profissional?",
        )

    if archetype == "bot_router_vendor_pitch":
        opening = "Ola, sou da Zind."
        context = (
            "Somos fornecedores de um sistema para sindicos profissionais, "
            "pensado para o dia a dia da sindicatura."
        )
        cta_line = (
            "Se fizer sentido, envio um video rapido, o site da Zind e 3 artigos do blog."
        )
        return _normalize_spaces(opening), _normalize_spaces(context), _normalize_spaces(cta_line)

    compact_signal = f" Vi um sinal recente: {_clip(signal_text, 72)}." if signal_text else ""
    compact_pain = _clip(pain, 88)
    compact_company = _clip(company, 42)
    opening = _normalize_spaces(f"Oi {first_name}, tudo bem?{compact_signal}")
    context = _normalize_spaces(f"Como voces estao lidando com {compact_pain} na {compact_company}?")
    value = _normalize_spaces(f"Tenho um caminho simples para {objective}.")
    if "pain" in archetype:
        value = _normalize_spaces(f"Vi que isso costuma travar rotina e gerar retrabalho. {value}")
    if "signal" in archetype:
        value = _normalize_spaces(f"Te chamei por causa desse sinal recente. {value}")
    cta_line = _normalize_spaces(f"Topa {cta}?")
    return _normalize_spaces(f"{opening} {context}"), value, cta_line


def _split_by_words(text: str, limit: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
            continue
        chunks.append(current)
        current = word
    chunks.append(current)
    return chunks


def _split_whatsapp_messages(
    *,
    draft: str,
    part_a: str,
    part_b: str,
    part_cta: str,
    split_after: int,
) -> tuple[list[str], bool]:
    if len(draft) <= split_after:
        return [draft], False

    two_chunks = [part_a, _normalize_spaces(f"{part_b} {part_cta}")]
    if all(len(chunk) <= split_after for chunk in two_chunks):
        return two_chunks, True

    three_chunks = [part_a, part_b, part_cta]
    expanded: list[str] = []
    for chunk in three_chunks:
        if not chunk:
            continue
        if len(chunk) <= split_after:
            expanded.append(chunk)
            continue
        expanded.extend(_split_by_words(chunk, split_after))

    if len(expanded) > 3:
        merged_tail = _normalize_spaces(" ".join(expanded[2:]))
        if len(merged_tail) > split_after:
            merged_tail = _clip(merged_tail, split_after)
        expanded = expanded[:2] + [merged_tail]

    return expanded, True


def _apply_humanity_checks(messages: list[str], channel: str) -> dict[str, Any]:
    rules = _load_json("human_rules.json")
    max_chars = rules["max_chars_whatsapp"] if channel == "whatsapp" else rules["max_chars_email"]
    target_min = rules.get("target_min_whatsapp_chars", 140)
    target_max = rules.get("target_max_whatsapp_chars", 180)
    split_after = rules.get("split_after_whatsapp_chars", 220)
    forbidden = [x.lower() for x in rules.get("forbidden_patterns", [])]
    joined = "\n".join(messages)
    normalized = joined.lower()
    found_forbidden = [pattern for pattern in forbidden if pattern in normalized]
    lengths = [len(message) for message in messages]
    in_target_window = [target_min <= length <= target_max for length in lengths]
    return {
        "length_ok": all(length <= max_chars for length in lengths),
        "forbidden_hits": found_forbidden,
        "humanity_ok": len(found_forbidden) == 0 and all(length <= max_chars for length in lengths),
        "max_chars": max_chars,
        "target_min_chars": target_min,
        "target_max_chars": target_max,
        "split_after_chars": split_after,
        "messages_count": len(messages),
        "message_lengths": lengths,
        "messages_in_target_window": in_target_window,
    }


def build_personalized_draft(contato: Any, channel: str = "whatsapp", strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = _load_json("identity_soul.json")
    playbook = _pick_stage_playbook(getattr(contato, "pipeline_status", None))
    first_name = _resolve_first_name(contato)
    company = (getattr(contato, "empresa", None) or "sua operacao").strip()
    pain = _resolve_pain_hint(contato)
    signal = (getattr(contato, "recent_signal", None) or "").strip()
    signal_text = signal
    strategy = strategy or {}
    message_archetype = strategy.get("message_archetype", "stage_global_default")
    template_hint = strategy.get("template_hint", playbook.get("template_hint", ""))
    strategy_key = strategy.get("strategy_key")

    part_a, part_b, part_cta = _build_message_parts(
        first_name=first_name,
        signal_text=signal_text,
        pain=pain,
        company=company,
        objective=playbook["objective"],
        cta=playbook["cta"],
        template_hint=template_hint,
        archetype=message_archetype,
    )
    draft = _normalize_spaces(f"{part_a} {part_b} {part_cta}")

    rules = _load_json("human_rules.json")
    split_after = int(rules.get("split_after_whatsapp_chars", 220))
    if channel == "whatsapp" and message_archetype == "human_direct_probe_3step":
        messages = [chunk for chunk in [part_a, part_b, part_cta] if chunk]
        split_applied = len(messages) > 1
    elif channel == "whatsapp":
        messages, split_applied = _split_whatsapp_messages(
            draft=draft,
            part_a=part_a,
            part_b=part_b,
            part_cta=part_cta,
            split_after=split_after,
        )
    else:
        messages, split_applied = [draft], False

    checks = _apply_humanity_checks(messages, channel)
    checks["cta_only_last_chunk"] = all(playbook["cta"] not in chunk for chunk in messages[:-1]) if len(messages) > 1 else True
    checks["anti_text_wall"] = not (channel == "whatsapp" and len(draft) > split_after and len(messages) == 1)
    checks["humanity_ok"] = bool(
        checks["humanity_ok"]
        and checks["cta_only_last_chunk"]
        and checks["anti_text_wall"]
    )

    return {
        "channel": channel,
        "voice": identity.get("voice"),
        "stage_objective": playbook.get("objective"),
        "stage_cta": playbook.get("cta"),
        "template_hint": playbook.get("template_hint"),
        "strategy_key": strategy_key,
        "message_archetype": message_archetype,
        "confidence": strategy.get("confidence", 0.0),
        "retrieval_level": strategy.get("retrieval_level"),
        "draft": draft,
        "messages": messages,
        "split_applied": split_applied,
        "checks": checks,
    }
