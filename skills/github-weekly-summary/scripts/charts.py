"""
Script: charts.py
Função: Gera ASCII charts e listas formatadas para mensagens Discord
Usar quando: Antes de enviar o relatório para o Discord

ENV_VARS:
  - (nenhuma)

DB_TABLES:
  - (nenhuma)
"""

_STATUS_ORDER = [
    "backlog", "triage", "tarefas pendentes", "blocked",
    "em análise", "em andamento",
    "ready for test", "in test",
    "ready for prod",
    "reaberto",
    "concluído", "rejeitada",
]

_MONTHS_PT = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}


def _bar(value, max_value, width=20):
    filled = round(value / max_value * width) if max_value > 0 else 0
    return "█" * filled + "░" * (width - filled)


def _truncate(text, max_len=55):
    text = text or ""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# ---------------------------------------------------------------------------
# Velocity
# ---------------------------------------------------------------------------

def render_velocity_ascii(velocity_data, weeks=10):
    """
    Bar chart de throughput semanal — inclui semanas com 0 entrega.
    """
    throughput = velocity_data.get("weekly_throughput", {})
    avg = velocity_data.get("avg_weekly_throughput", 0)
    trend = velocity_data.get("trend", "estavel")
    trend_symbol = {"acelerando": "↑", "desacelerando": "↓", "estavel": "→"}.get(trend, "→")

    weeks_sorted = sorted(throughput.keys())[-weeks:]
    if not weeks_sorted:
        return ""

    max_val = max((throughput[w] for w in weeks_sorted), default=1) or 1

    lines = ["```", "Velocity — últimas {} semanas".format(len(weeks_sorted))]
    lines.append("─" * 34)
    for w in weeks_sorted:
        count = throughput[w]
        label = w.split("-W")[-1] if "-W" in w else w[-3:]
        marker = " <" if w == weeks_sorted[-1] else "  "
        lines.append("W{:<4} {}  {:>3}{}".format(label, _bar(count, max_val), count, marker))
    lines.append("─" * 34)
    lines.append("Média: {}/sem  Tendência: {} {}".format(avg, trend_symbol, trend))
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lead Time
# ---------------------------------------------------------------------------

def render_lead_time_ascii(velocity_data):
    """
    Compara p50 e p85 globais num bloco visual simples.
    """
    p50 = velocity_data.get("lead_time_p50")
    p85 = velocity_data.get("lead_time_p85")
    if p50 is None or p85 is None:
        return ""

    max_val = p85 or 1
    lines = ["```", "Lead Time  (criação → entrega)"]
    lines.append("─" * 34)
    lines.append("p50 (mediana) {}  {:.0f}d".format(_bar(p50, max_val), p50))
    lines.append("p85 (90% <=)  {}  {:.0f}d".format(_bar(p85, max_val), p85))
    lines.append("─" * 34)
    lines.append("Metade das entregas levam até {:.0f}d".format(p50))
    lines.append("90% das entregas levam até {:.0f}d".format(p85))
    lines.append("```")
    return "\n".join(lines)


def render_lead_time_trend_ascii(velocity_data):
    """
    Bar chart de lead time p50 por mês — mostra se está caindo ou subindo.
    """
    by_period = velocity_data.get("lead_time_by_period", {})
    if not by_period:
        return ""

    periods = sorted(by_period.keys())
    values = [by_period[p]["p50"] for p in periods if by_period[p]["p50"] is not None]
    if not values:
        return ""

    max_val = max(values) or 1

    # Tendência: compara último mês com penúltimo
    trend = ""
    if len(values) >= 2:
        diff = values[-1] - values[-2]
        if diff < -2:
            trend = "↓ caindo"
        elif diff > 2:
            trend = "↑ subindo"
        else:
            trend = "→ estável"

    lines = ["```", "Lead Time p50 por mês  (criação → entrega)"]
    lines.append("─" * 38)
    for p in periods:
        val = by_period[p]["p50"]
        if val is None:
            continue
        year, month = p.split("-")
        label = "{}/{}".format(_MONTHS_PT.get(month, month), year[2:])
        count = by_period[p]["count"]
        lines.append("{:<7} {}  {:>4.0f}d  ({} itens)".format(label, _bar(val, max_val, 16), val, count))
    lines.append("─" * 38)
    if trend:
        lines.append("Tendência: {}".format(trend))
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WIP Aging
# ---------------------------------------------------------------------------

_WIP_LABELS = {
    "fresh":    "Fresh   <7d  | recém iniciado",
    "normal":   "Normal  7-14d| em ritmo saudável",
    "at_risk":  "Atenção 15-30| pode travar",
    "blocked":  "Parado  >30d | precisa de ação",
}

_WIP_LABEL_SHORT = {
    "fresh":   "Fresh   (<7d) ",
    "normal":  "Normal  (7-14)",
    "at_risk": "Atencao(15-30)",
    "blocked": "Parado  (>30d)",
}


def render_wip_ascii(wip_data):
    """
    Bar chart de WIP aging com legenda descritiva de cada faixa.
    """
    total = wip_data.get("total_wip", 0)
    items = wip_data.get("items", [])
    if not items:
        return ""

    buckets = ["fresh", "normal", "at_risk", "blocked"]
    counts = {k: sum(1 for i in items if i.get("risk_level") == k) for k in buckets}
    max_val = max(counts.values()) or 1

    lines = ["```", "WIP Aging — {} itens em andamento".format(total)]
    lines.append("─" * 38)
    for key in buckets:
        count = counts[key]
        lines.append("{}  {}  {:>3}".format(_WIP_LABEL_SHORT[key], _bar(count, max_val), count))
    lines.append("─" * 38)
    lines.append("Fresh=recém iniciado  Normal=saudável")
    lines.append("Atencao=pode travar   Parado=precisa de ação")
    blocked = wip_data.get("blocked_count", 0)
    at_risk = wip_data.get("at_risk_count", 0)
    alerts = []
    if blocked:
        alerts.append("{} parados >30d".format(blocked))
    if at_risk:
        alerts.append("{} em atenção".format(at_risk))
    if alerts:
        lines.append("⚠ " + "  |  ".join(alerts))
    lines.append("```")
    return "\n".join(lines)


def render_wip_list(wip_data, max_items=15):
    """
    Lista os itens em andamento, priorizando os mais antigos (bloqueados primeiro).
    Mostra apenas itens com risco = at_risk ou blocked, limitado a max_items.
    """
    items = wip_data.get("items", [])
    prioritized = [i for i in items if i.get("risk_level") in ("blocked", "at_risk")]
    prioritized.sort(key=lambda x: x.get("aging_days") or 0, reverse=True)
    prioritized = prioritized[:max_items]

    if not prioritized:
        return ""

    lines = ["**WIP — itens que precisam de atenção ({} de {})**".format(
        len(prioritized), wip_data.get("total_wip", 0))]
    lines.append("```")
    for i in prioritized:
        tag = "PARADO" if i.get("risk_level") == "blocked" else "ATENC."
        assignee = (i.get("assignee") or "—")[:12]
        lines.append("[{}] [{}] {:<45} {:>3}d  {}".format(
            tag,
            i.get("key", ""),
            _truncate(i.get("summary", ""), 45),
            i.get("aging_days") or 0,
            assignee,
        ))
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Listas semanais
# ---------------------------------------------------------------------------

def render_delivered_list(jira_data):
    """
    Lista issues finalizadas esta semana com ciclo de vida.
    """
    done = [i for i in jira_data if i.get("status_category") == "done"]
    if not done:
        return "**Entregues esta semana:** nenhuma entrega registrada."

    lines = ["**Entregues esta semana ({}):**".format(len(done)), "```"]
    for i in done:
        cycle = "{:.0f}d".format(i["cycle_time_days"]) if i.get("cycle_time_days") is not None else "—"
        assignee = (i.get("assignee") or "—")[:12]
        lines.append("[{}] {:<50} ciclo:{:>5}  {}".format(
            i.get("key", ""),
            _truncate(i.get("summary", ""), 50),
            cycle,
            assignee,
        ))
    lines.append("```")
    return "\n".join(lines)


def render_state_changes_list(jira_data, max_items=20):
    """
    Lista issues que mudaram de estado esta semana (com as transições).
    """
    with_changes = [i for i in jira_data if i.get("state_changes")]
    with_changes.sort(key=lambda x: len(x.get("state_changes", [])), reverse=True)
    with_changes = with_changes[:max_items]

    if not with_changes:
        return "**Mudanças de estado esta semana:** nenhuma."

    lines = ["**Mudanças de estado esta semana ({}):**".format(len(with_changes)), "```"]
    for i in with_changes:
        changes = i.get("state_changes", [])
        last = changes[-1] if changes else {}
        arrow = "{} → {}".format(last.get("from", "?"), last.get("to", "?"))
        lines.append("[{}] {:<42} {}".format(
            i.get("key", ""),
            _truncate(i.get("summary", ""), 42),
            arrow,
        ))
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cycle Time Kanban (Em andamento → READY FOR PROD)
# ---------------------------------------------------------------------------

def render_cycle_time_trend_ascii(velocity_data):
    """
    Bar chart de cycle time p50 por mês — mostra se está melhorando ou piorando.
    """
    by_period = velocity_data.get("cycle_time_by_period", {})
    if not by_period:
        return ""

    periods = sorted(by_period.keys())
    values = [by_period[p]["p50"] for p in periods if by_period[p].get("p50") is not None]
    if not values:
        return ""

    max_val = max(values) or 1
    trend = ""
    if len(values) >= 2:
        diff = values[-1] - values[-2]
        if diff < -2:
            trend = "↓ melhorando"
        elif diff > 2:
            trend = "↑ piorando"
        else:
            trend = "→ estável"

    lines = ["```", "Cycle Time p50 por mês  (In Progress → READY FOR PROD)"]
    lines.append("─" * 40)
    for p in periods:
        val = by_period[p].get("p50")
        if val is None:
            continue
        year, month = p.split("-")
        label = "{}/{}".format(_MONTHS_PT.get(month, month), year[2:])
        count = by_period[p]["count"]
        lines.append("{:<7} {}  {:>4.0f}d  ({} itens)".format(
            label, _bar(val, max_val, 16), val, count))
    lines.append("─" * 40)
    if trend:
        lines.append("Tendência: {}".format(trend))
    lines.append("```")
    return "\n".join(lines)


def render_stage_count_ascii(stage_data):
    """
    Resumo consolidado: quantos tickets há em cada etapa do fluxo.
    Inclui todas as etapas, não só as ativas.
    """
    if not stage_data:
        return ""

    stage_order = ["In Progress", "In Review", "Ready for Test", "In Test", "READY FOR PROD"]
    counts = {s: stage_data.get(s, {}).get("count", 0) for s in stage_order}
    avgs   = {s: stage_data.get(s, {}).get("avg_days") for s in stage_order}
    total  = sum(counts.values())
    max_c  = max(counts.values()) or 1

    lines = ["```", "Tickets por etapa  (total em andamento: {})".format(total)]
    lines.append("─" * 44)
    for s in stage_order:
        c   = counts[s]
        avg = avgs[s]
        avg_str = "  avg {:.0f}d".format(avg) if avg is not None else ""
        lines.append("{:<20} {}  {:>3}{}".format(
            s, _bar(c, max_c, 16), c, avg_str))
    lines.append("─" * 44)
    lines.append("```")
    return "\n".join(lines)


def render_wip_per_person_ascii(stage_data, max_people=15):
    """
    Agrega WIP por assignee em todas as etapas ativas.
    Mostra quantos itens cada pessoa tem no board e em quais etapas.
    """
    from collections import defaultdict
    person_stages: dict = defaultdict(lambda: defaultdict(int))
    stage_order = ["In Progress", "In Review", "Ready for Test", "In Test", "READY FOR PROD"]

    for stage in stage_order:
        data = stage_data.get(stage, {})
        for item in data.get("items", []):
            name = item.get("assignee") or "—"
            person_stages[name][stage] += 1

    if not person_stages:
        return ""

    # Total por pessoa, ordenado descrescente
    totals = {p: sum(s.values()) for p, s in person_stages.items()}
    ranked = sorted(totals.items(), key=lambda x: -x[1])[:max_people]
    max_total = ranked[0][1] if ranked else 1

    # Siglas de coluna
    abbr = {"In Progress": "Prog", "In Review": "Rev", "Ready for Test": "RfT",
            "In Test": "Test", "READY FOR PROD": "Prod"}

    lines = ["```", "WIP por pessoa  (etapas ativas)"]
    lines.append("─" * 50)
    header = "{:<18}  {}  {}".format("Pessoa", "  ".join(f"{abbr[s]:>4}" for s in stage_order), "Total")
    lines.append(header)
    lines.append("─" * 50)

    for person, total in ranked:
        stages = person_stages[person]
        counts = "  ".join(f"{stages.get(s, 0):>4}" for s in stage_order)
        bar = _bar(total, max_total, 10)
        lines.append("{:<18}  {}  {} {}".format(
            _truncate(person, 18), counts, bar, total))

    lines.append("─" * 50)
    lines.append("Prog=In Progress  Rev=In Review  RfT=Ready for Test")
    lines.append("```")
    return "\n".join(lines)


def render_stage_detail_ascii(stage_data, max_items_per_stage=8):
    """
    Para cada etapa de trabalho, mostra itens e tempo no status atual.
    Destaca itens parados há mais de 14 dias.
    """
    if not stage_data:
        return ""

    parts = []
    for stage, data in stage_data.items():
        items = data.get("items", [])
        count = data.get("count", 0)
        avg = data.get("avg_days")

        if count == 0:
            continue

        avg_str = "  avg: {}d".format(int(avg)) if avg else ""
        header = "**{} ({} itens{})**".format(stage, count, avg_str)
        lines = [header, "```"]

        shown = items[:max_items_per_stage]
        for i in shown:
            days = i.get("days_in_stage")
            assignee = (i.get("assignee") or "—")[:12]
            flag = " !" if days and days > 14 else "  "
            days_str = "{:>3}d".format(days) if days is not None else "  —d"
            lines.append("[{}]{} {:<48} {}  {}".format(
                i.get("key", ""),
                flag,
                _truncate(i.get("summary", ""), 48),
                days_str,
                assignee,
            ))
        if count > max_items_per_stage:
            lines.append("  ... +{} mais".format(count - max_items_per_stage))
        lines.append("```")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def render_cycle_time_kanban_ascii(rework_data):
    """
    Mostra distribuição do Cycle Time real do time (Em andamento → READY FOR PROD).
    """
    p50 = rework_data.get("cycle_time_p50")
    p85 = rework_data.get("cycle_time_p85")
    avg = rework_data.get("avg_cycle_time_days")

    if p50 is None and avg is None:
        return ""

    ref = p85 or avg or 1
    lines = ["```", "Cycle Time  (Em andamento → READY FOR PROD)"]
    lines.append("─" * 42)
    if avg is not None:
        lines.append("Média  {}  {:.0f}d".format(_bar(avg, ref), avg))
    if p50 is not None:
        lines.append("p50    {}  {:.0f}d".format(_bar(p50, ref), p50))
    if p85 is not None:
        lines.append("p85    {}  {:.0f}d".format(_bar(p85, ref), p85))
    lines.append("─" * 42)
    if p50:
        lines.append("Metade das entregas prontas em até {:.0f}d".format(p50))
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Flow Efficiency, Time in Status, Queue Time
# ---------------------------------------------------------------------------

def render_flow_efficiency_ascii(rework_data):
    """
    Mostra como o Lead Time se divide entre trabalho real e espera.
    """
    avg_lead  = rework_data.get("avg_lead_time_days")
    avg_cycle = rework_data.get("avg_cycle_time_days")
    avg_queue = rework_data.get("avg_queue_time_days")
    avg_lag   = rework_data.get("avg_deploy_lag_days")
    flow_eff  = rework_data.get("flow_efficiency_pct")

    if avg_lead is None or avg_cycle is None:
        return ""

    max_val = avg_lead or 1
    lines = ["```", "Flow Efficiency  (Cycle Time / Lead Time)"]
    lines.append("─" * 42)
    lines.append("Lead Time (total)  {}  {:.0f}d".format(_bar(avg_lead,  max_val), avg_lead))
    lines.append("Cycle Time (work)  {}  {:.0f}d".format(_bar(avg_cycle, max_val), avg_cycle))
    if avg_queue is not None:
        lines.append("Queue Time (fila)  {}  {:.0f}d".format(_bar(avg_queue, max_val), avg_queue))
    if avg_lag is not None:
        lines.append("Deploy Lag         {}  {:.0f}d".format(_bar(avg_lag, max_val), avg_lag))
    lines.append("─" * 42)
    if flow_eff is not None:
        lines.append("Flow Efficiency: {:.0f}%  ({:.0f}% do tempo é espera)".format(
            flow_eff, 100 - flow_eff))
    lines.append("```")
    return "\n".join(lines)


def render_time_in_status_ascii(rework_data):
    """
    Bar chart de tempo médio em cada coluna — mostra onde está o gargalo.
    """
    avg_tis = rework_data.get("avg_time_in_status", {})
    if not avg_tis:
        return ""

    # Ordena pelos status canônicos, coloca o resto no fim
    ordered = []
    seen = set()
    for s in _STATUS_ORDER:
        for actual_status, days in avg_tis.items():
            if actual_status.lower().strip() == s and actual_status not in seen:
                ordered.append((actual_status, days))
                seen.add(actual_status)
    for s, d in sorted(avg_tis.items(), key=lambda x: -x[1]):
        if s not in seen:
            ordered.append((s, d))

    if not ordered:
        return ""

    max_val = max(d for _, d in ordered) or 1
    bottleneck = max(ordered, key=lambda x: x[1])

    lines = ["```", "Tempo médio por etapa  (gargalo: {} — {:.0f}d)".format(
        bottleneck[0], bottleneck[1])]
    lines.append("─" * 44)
    for status, days in ordered:
        marker = " <" if status == bottleneck[0] else "  "
        lines.append("{:<20} {}  {:>4.0f}d{}".format(
            status[:20], _bar(days, max_val, 16), days, marker))
    lines.append("─" * 44)
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deploy Lag e Retrabalho
# ---------------------------------------------------------------------------

def render_deploy_lag_ascii(rework_data):
    """
    Mostra tempo médio entre READY FOR PROD e Concluído.
    """
    avg = rework_data.get("avg_deploy_lag_days")
    p50 = rework_data.get("deploy_lag_p50")
    p85 = rework_data.get("deploy_lag_p85")
    total = rework_data.get("deploy_lag_total", 0)
    items = rework_data.get("deploy_lag_items", [])

    if avg is None or total == 0:
        return "**Deploy Lag:** nenhum item passou por READY FOR PROD → Concluído no período."

    max_val = p85 or avg or 1
    lines = ["```", "Deploy Lag  (READY FOR PROD → Concluído)  — {} itens".format(total)]
    lines.append("─" * 42)
    lines.append("Média  {}  {:.0f}d".format(_bar(avg, max_val), avg))
    if p50 is not None:
        lines.append("p50    {}  {:.0f}d".format(_bar(p50, max_val), p50))
    if p85 is not None:
        lines.append("p85    {}  {:.0f}d".format(_bar(p85, max_val), p85))
    lines.append("─" * 42)
    if items:
        lines.append("Maiores lags:")
        for i in items[:5]:
            lines.append("  [{:<8}] {:.<42} {:>3}d".format(
                i.get("key", ""), _truncate(i.get("summary", ""), 42) + " ", int(i.get("days", 0))
            ))
    lines.append("```")
    return "\n".join(lines)


def render_rework_breakdown_ascii(breakdown_data, max_items=8):
    """
    Mostra retrabalho por tipo de transição backward com lista de itens.
    """
    if not breakdown_data:
        return ""

    total_items = breakdown_data.get("total_items_with_rework", 0)
    total_occ   = breakdown_data.get("total_occurrences", 0)
    weeks       = breakdown_data.get("weeks_back", 16)
    by_type     = breakdown_data.get("by_type", {})

    if total_items == 0:
        return "**Retrabalho:** nenhuma transição backward detectada nos últimos {} semanas.".format(weeks)

    label_map = {
        "review_rejection": "Review → Dev   (code review rejeitado)",
        "qa_rejection":     "QA → Dev       (QA/teste rejeitou)",
        "reopened":         "→ REOPENED     (qualquer etapa)",
        "other_backward":   "Outro backward",
    }

    parts = []

    # Resumo
    summary_lines = ["```", "Retrabalho — últimas {} semanas".format(weeks)]
    summary_lines.append("─" * 42)
    summary_lines.append("{} itens afetados  |  {} ocorrências totais".format(total_items, total_occ))
    summary_lines.append("─" * 42)

    max_occ = max((d["total_occurrences"] for d in by_type.values()), default=1)
    for cat, data in sorted(by_type.items(), key=lambda x: -x[1]["total_occurrences"]):
        label = label_map.get(cat, cat)
        occ   = data["total_occurrences"]
        n     = len(data["items"])
        summary_lines.append("{:<40} {}  {:>2}x ({} itens)".format(
            label, _bar(occ, max_occ, 8), occ, n))

    summary_lines.append("```")
    parts.append("\n".join(summary_lines))

    # Detalhe por tipo
    for cat, data in sorted(by_type.items(), key=lambda x: -x[1]["total_occurrences"]):
        label = label_map.get(cat, cat)
        items = data["items"][:max_items]
        lines = ["**{}** ({} itens, {} ocorrências)".format(
            label, len(data["items"]), data["total_occurrences"]), "```"]
        for i in items:
            times = "{}x".format(i["count"])
            assignee = (i.get("assignee") or "—")[:12]
            lines.append("[{}] {:<48} {}  {}".format(
                i.get("key", ""),
                _truncate(i.get("summary", ""), 48),
                times, assignee,
            ))
        if len(data["items"]) > max_items:
            lines.append("  ... +{} mais".format(len(data["items"]) - max_items))
        lines.append("```")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def render_rework_ascii(rework_data):
    """
    Mostra taxa de retrabalho (itens que voltaram de teste para dev).
    """
    total = rework_data.get("total_analyzed", 0)
    rework_total = rework_data.get("rework_total", 0)
    rate = rework_data.get("rework_rate_pct", 0)
    weeks = rework_data.get("weeks_back", 8)
    items = rework_data.get("rework_items", [])

    if total == 0:
        return "**Retrabalho:** sem dados suficientes."

    bar_rework = _bar(rework_total, total)
    bar_clean   = _bar(total - rework_total, total)

    lines = ["```", "Retrabalho  (In Test / Ready for Test → dev)  — últimas {} semanas".format(weeks)]
    lines.append("─" * 46)
    lines.append("Sem retrab.  {}  {} issues".format(bar_clean,  total - rework_total))
    lines.append("Com retrab.  {}  {} issues  ({:.0f}%)".format(bar_rework, rework_total, rate))
    lines.append("─" * 46)
    if items:
        lines.append("Itens com mais retrabalho:")
        for i in items[:5]:
            times = i.get("rework_count", 0)
            label = "{}x".format(times)
            lines.append("  [{:<8}] {:.<42} {}".format(
                i.get("key", ""), _truncate(i.get("summary", ""), 42) + " ", label
            ))
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sample_velocity = {
        "weekly_throughput": {
            "2026-W01": 0,  "2026-W02": 0,  "2026-W03": 5,
            "2026-W04": 0,  "2026-W05": 12, "2026-W06": 0,
            "2026-W07": 1,  "2026-W08": 41, "2026-W09": 3,
            "2026-W10": 2,  "2026-W11": 0,  "2026-W12": 59,
            "2026-W13": 0,  "2026-W14": 0,  "2026-W15": 0,
            "2026-W16": 0,  "2026-W17": 1,  "2026-W18": 0,
        },
        "avg_weekly_throughput": 6.9,
        "trend": "acelerando",
        "lead_time_p50": 39.9,
        "lead_time_p85": 98.0,
        "lead_time_by_period": {
            "2026-01": {"p50": 55.0, "p85": 110.0, "count": 12},
            "2026-02": {"p50": 48.0, "p85": 95.0,  "count": 18},
            "2026-03": {"p50": 42.0, "p85": 88.0,  "count": 41},
            "2026-04": {"p50": 35.0, "p85": 75.0,  "count": 36},
        },
    }
    sample_wip = {
        "total_wip": 98,
        "blocked_count": 85,
        "at_risk_count": 1,
        "items": (
            [{"risk_level": "fresh",   "key": "ZIN-600", "summary": "Nova feature X",      "aging_days": 3,  "assignee": "mateus"}] * 1 +
            [{"risk_level": "normal",  "key": "ZIN-580", "summary": "Ajuste de UI",         "aging_days": 10, "assignee": "philipe"}] * 11 +
            [{"risk_level": "at_risk", "key": "ZIN-518", "summary": "Tela operacional",      "aging_days": 30, "assignee": "mateus"}] * 1 +
            [{"risk_level": "blocked", "key": "ZIN-001", "summary": "Item muito antigo aqui","aging_days": 233,"assignee": "amir"}] * 85
        ),
    }
    sample_jira = [
        {"key": "ZIN-500", "summary": "Divisão em tickets do documento",
         "status_category": "done", "cycle_time_days": 34.2, "assignee": "mateus",
         "state_changes": [{"from": "Backlog", "to": "Done"}]},
        {"key": "ZIN-490", "summary": "Auto selecionar condominio",
         "status_category": "indeterminate", "cycle_time_days": None, "assignee": "mateus",
         "state_changes": [{"from": "Em análise", "to": "Ready for Test"}]},
    ]

    print(render_velocity_ascii(sample_velocity))
    print()
    print(render_lead_time_trend_ascii(sample_velocity))
    print()
    print(render_lead_time_ascii(sample_velocity))
    print()
    print(render_wip_ascii(sample_wip))
    print()
    print(render_wip_list(sample_wip, max_items=5))
    print()
    print(render_delivered_list(sample_jira))
    print()
    print(render_state_changes_list(sample_jira))
