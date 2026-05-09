"""
Script: fetch_jira_issues.py
Função: Busca issues Jira com movimentação na última semana, velocity dos últimos 4 meses e WIP aging
Usar quando: Coleta semanal de dados Jira para o pipeline github-weekly-summary

ENV_VARS:
  - JIRA_TOKEN: API token do Atlassian
  - JIRA_BASE_URL: URL base do Jira (ex: https://empresa.atlassian.net)
  - JIRA_EMAIL: e-mail cadastrado no Jira
  - JIRA_PROJECT_KEY: chave do projeto Jira (ex: ABC)

DB_TABLES:
  - (nenhuma)
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "")


def _resolve_jira_token():
    """Retorna o primeiro token que autentica com sucesso em /rest/api/3/myself."""
    candidates = [
        os.environ.get("JIRA_TOKEN", ""),
        os.environ.get("JIRA_TESTE_TOKEN", ""),
    ]
    for token in candidates:
        if not token:
            continue
        try:
            r = requests.get(
                f"{JIRA_URL}/rest/api/3/myself",
                auth=(JIRA_EMAIL, token),
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if r.status_code == 200:
                return token
        except Exception:
            continue
    return candidates[0] if candidates[0] else candidates[1]


JIRA_TOKEN = _resolve_jira_token()

# Status do projeto ZIN mapeados via /rest/api/3/project/{key}/statuses
_READY_FOR_PROD       = {"ready for prod"}
_DONE_STATUSES        = {"concluído", "rejeitada"}
_IN_PROGRESS_STATUSES = {"em andamento", "in progress"}

# Fluxo forward — qualquer transição que recua nessa ordem é retrabalho
_FORWARD_STAGES = ["in progress", "in review", "ready for test", "in test", "ready for prod"]

# Ordem canônica para o gráfico de Time in Status
_STATUS_ORDER = [
    "backlog", "triage", "tarefas pendentes", "blocked",
    "em análise", "em andamento", "in progress",
    "in review", "ready for test", "in test",
    "ready for prod", "reaberto",
    "concluído", "rejeitada",
]

_REWORK_LABELS = {
    "review_rejection": "Review → Dev     (code review rejeitado)",
    "qa_rejection":     "QA → Dev         (QA rejeitou)",
    "reopened":         "→ REOPENED       (qualquer etapa)",
    "other_backward":   "Outro backward",
}


def _classify_rework(from_status, to_status):
    """Retorna categoria de retrabalho ou None."""
    frm = (from_status or "").lower().strip()
    to  = (to_status   or "").lower().strip()

    if to == "reaberto":
        return "reopened"

    try:
        from_idx = _FORWARD_STAGES.index(frm)
        to_idx   = _FORWARD_STAGES.index(to)
        if to_idx < from_idx:
            if frm == "in review":
                return "review_rejection"
            elif frm in ("ready for test", "in test"):
                return "qa_rejection"
            return "other_backward"
    except ValueError:
        pass
    return None


def _count_rework(state_changes):
    """Conta total de transições de retrabalho."""
    return sum(1 for ch in state_changes
               if _classify_rework(ch.get("from"), ch.get("to")) is not None)


def _rework_breakdown(state_changes):
    """Retorna {categoria: count} para uma issue."""
    result: dict = {}
    for ch in state_changes:
        cat = _classify_rework(ch.get("from"), ch.get("to"))
        if cat:
            result[cat] = result.get(cat, 0) + 1
    return result


def _calc_deploy_lag(state_changes):
    """Dias entre última entrada em READY FOR PROD e primeira conclusão após ela."""
    ready_at = None
    for ch in state_changes:
        to = (ch.get("to") or "").lower().strip()
        if to in _READY_FOR_PROD:
            ready_at = ch.get("at")
        elif to in _DONE_STATUSES and ready_at is not None:
            return _calc_days(ready_at, ch.get("at"))
    return None


def _calc_queue_time(created_str, state_changes):
    """Dias de criação até a primeira entrada em 'Em andamento'."""
    for ch in state_changes:
        if (ch.get("to") or "").lower().strip() in _IN_PROGRESS_STATUSES:
            return _calc_days(created_str, ch.get("at"))
    return None


def _calc_cycle_time_kanban(state_changes):
    """Dias da última entrada em 'Em andamento' até entrada em READY FOR PROD."""
    started_at = None
    for ch in state_changes:
        to = (ch.get("to") or "").lower().strip()
        if to in _IN_PROGRESS_STATUSES:
            started_at = ch.get("at")         # atualiza para a última vez que entrou
        elif to in _READY_FOR_PROD and started_at is not None:
            return _calc_days(started_at, ch.get("at"))
    return None


def _calc_time_in_status(created_str, state_changes, resolved_str=None):
    """
    Retorna {status: days} acumulando tempo em cada coluna.
    Usa timestamps consecutivos do changelog.
    """
    times = {}

    def _add(status, days):
        if status and days is not None and days >= 0:
            times[status] = times.get(status, 0) + days

    if state_changes:
        _add(state_changes[0].get("from", ""), _calc_days(created_str, state_changes[0].get("at")))

    for i, ch in enumerate(state_changes):
        entered = ch.get("to", "")
        entered_at = ch.get("at")
        left_at = state_changes[i + 1].get("at") if i + 1 < len(state_changes) else resolved_str
        if entered_at and left_at:
            _add(entered, _calc_days(entered_at, left_at))

    return times


def _jql_search(jql, fields, max_results=200):
    """
    Pagina o endpoint /rest/api/3/search/jql usando cursor (nextPageToken).
    Esse endpoint NÃO aceita startAt — usa isLast + nextPageToken.
    """
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    issues = []
    next_page_token = None
    while True:
        payload = {
            "jql": jql,
            "fields": fields,
            "maxResults": min(100, max_results - len(issues)),
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        resp = requests.post(url, auth=auth, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)
        if data.get("isLast", True) or not batch or len(issues) >= max_results:
            break
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    return issues


def _get_changelog(issue_key):
    """Busca o histórico de mudanças de status de uma issue."""
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    headers = {"Accept": "application/json"}
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/changelog"
    resp = requests.get(url, auth=auth, headers=headers, timeout=30)
    if resp.status_code != 200:
        return []
    status_changes = []
    for entry in resp.json().get("values", []):
        for item in entry.get("items", []):
            if item.get("field") == "status":
                status_changes.append({
                    "from": item.get("fromString"),
                    "to": item.get("toString"),
                    "at": entry.get("created"),
                    "author": (entry.get("author") or {}).get("displayName"),
                })
    return status_changes


def _calc_days(start_str, end_str):
    """Calcula dias corridos entre duas datas ISO."""
    try:
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        return round((end - start).total_seconds() / 86400, 1)
    except Exception:
        return None


def _percentile(sorted_data, pct):
    if not sorted_data:
        return None
    idx = max(0, int(len(sorted_data) * pct / 100) - 1)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# ---------------------------------------------------------------------------
# Coleta semanal (últimos 7 dias)
# ---------------------------------------------------------------------------

def fetch_weekly_jira_issues():
    """
    Retorna issues com movimentação na última semana.
    Cada item inclui state_changes e cycle_time_days quando aplicável.
    """
    jql = f"project = {JIRA_PROJECT_KEY} AND updated >= -7d ORDER BY updated DESC"
    fields = [
        "summary", "status", "created", "updated",
        "assignee", "statuscategorychangedate", "priority",
    ]

    raw_issues = _jql_search(jql, fields)
    result = []

    for issue in raw_issues:
        f = issue.get("fields", {})
        key = issue.get("key")
        category = f.get("status", {}).get("statusCategory", {}).get("key", "")
        done_at = f.get("statuscategorychangedate")
        created_at = f.get("created") or ""

        cycle_time = None
        if category == "done" and done_at and created_at:
            cycle_time = _calc_days(created_at, done_at)

        state_changes = _get_changelog(key)
        cycle_time_kanban = _calc_cycle_time_kanban(state_changes)
        queue_time = _calc_queue_time(created_at, state_changes)
        deploy_lag = _calc_deploy_lag(state_changes)
        lead_time_full = _calc_days(created_at, done_at) if (created_at and done_at) else None
        flow_efficiency = (
            round(cycle_time_kanban / lead_time_full * 100, 1)
            if cycle_time_kanban and lead_time_full and lead_time_full > 0
            else None
        )

        result.append({
            "key": key,
            "summary": f.get("summary"),
            "status": f.get("status", {}).get("name"),
            "status_category": category,
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "created": created_at,
            "updated": f.get("updated"),
            "done_at": done_at,
            "cycle_time_days": cycle_time,           # legado: created → done
            "cycle_time_kanban_days": cycle_time_kanban,  # Em andamento → READY FOR PROD
            "queue_time_days": queue_time,
            "deploy_lag_days": deploy_lag,
            "flow_efficiency_pct": flow_efficiency,
            "time_in_status": _calc_time_in_status(created_at, state_changes, done_at),
            "state_changes": state_changes,
            "rework_count": _count_rework(state_changes),
            "priority": (f.get("priority") or {}).get("name"),
        })

    return result


# ---------------------------------------------------------------------------
# Velocity histórico (últimos ~17 semanas / 4 meses)
# ---------------------------------------------------------------------------

def fetch_jira_velocity_history():
    """
    Conta entregas pela data em que o item entrou em READY FOR PROD (não resolutiondate).
    Isso reflete a realidade do time: READY FOR PROD = entregue, mesmo sem fechar o ticket.
    Para cada item busca o changelog e usa a data da ÚLTIMA entrada em READY FOR PROD.
    """
    jql = (
        f"project = {JIRA_PROJECT_KEY} "
        f'AND status CHANGED TO "READY FOR PROD" AFTER -120d '
        f"ORDER BY updated ASC"
    )
    fields = ["summary", "status", "created", "updated", "priority", "issuetype"]

    raw_issues = _jql_search(jql, fields, max_results=300)

    weekly_throughput = {}
    lead_times = []
    cycle_time_values = []
    queue_time_values = []
    monthly_lead_times = {}
    by_priority = {}
    by_issue_type = {}

    for issue in raw_issues:
        key = issue.get("key")
        f = issue.get("fields", {})
        created_str = f.get("created") or ""

        # Changelog já buscado — aproveita para todas as métricas
        state_changes = _get_changelog(key)

        # Delivery date = ÚLTIMA entrada em READY FOR PROD
        delivery_at = None
        for ch in reversed(state_changes):
            if (ch.get("to") or "").lower().strip() in _READY_FOR_PROD:
                delivery_at = ch.get("at")
                break

        if not delivery_at:
            continue

        try:
            delivery_dt = datetime.fromisoformat(delivery_at.replace("Z", "+00:00"))
            iso_week = delivery_dt.strftime("%Y-W%V")
            weekly_throughput[iso_week] = weekly_throughput.get(iso_week, 0) + 1
        except Exception:
            continue

        if created_str:
            lt = _calc_days(created_str, delivery_at)
            if lt is not None and lt >= 0:
                lead_times.append(lt)
                try:
                    month_key = delivery_dt.strftime("%Y-%m")
                    monthly_lead_times.setdefault(month_key, []).append(lt)
                except Exception:
                    pass

        # Cycle time: Em andamento → READY FOR PROD
        ct = _calc_cycle_time_kanban(state_changes)
        if ct is not None and ct >= 0:
            cycle_time_values.append(ct)

        # Queue time: criação → Em andamento
        qt = _calc_queue_time(created_str, state_changes)
        if qt is not None and qt >= 0:
            queue_time_values.append(qt)

        priority = (f.get("priority") or {}).get("name", "Sem prioridade")
        by_priority[priority] = by_priority.get(priority, 0) + 1

        issue_type = (f.get("issuetype") or {}).get("name", "Desconhecido")
        by_issue_type[issue_type] = by_issue_type.get(issue_type, 0) + 1

    lead_times.sort()

    # Preenche todas as semanas do período com 0 para não ter gaps no gráfico
    now = datetime.now(timezone.utc)
    full_throughput = {}
    for weeks_back in range(17, -1, -1):
        dt = now - timedelta(weeks=weeks_back)
        week_key = dt.strftime("%Y-W%V")
        full_throughput[week_key] = weekly_throughput.get(week_key, 0)

    counts = list(full_throughput.values())
    avg = round(sum(counts) / len(counts), 1) if counts else 0

    trend = "estavel"
    if len(counts) >= 4:
        mid = len(counts) // 2
        first_half_avg = sum(counts[:mid]) / mid
        second_half_avg = sum(counts[mid:]) / (len(counts) - mid)
        if second_half_avg > first_half_avg * 1.1:
            trend = "acelerando"
        elif second_half_avg < first_half_avg * 0.9:
            trend = "desacelerando"

    lead_time_by_period = {
        month: {
            "p50": _percentile(sorted(times), 50),
            "p85": _percentile(sorted(times), 85),
            "count": len(times),
        }
        for month, times in sorted(monthly_lead_times.items())
    }

    cycle_time_values.sort()
    queue_time_values.sort()

    # Cycle time por mês (mesma lógica do lead_time_by_period)
    monthly_cycle_times: dict = {}
    for issue in raw_issues:
        key = issue.get("key")
        f = issue.get("fields", {})
        created_str = f.get("created") or ""
        state_changes = _get_changelog(key)
        delivery_at = None
        for ch in reversed(state_changes):
            if (ch.get("to") or "").lower().strip() in _READY_FOR_PROD:
                delivery_at = ch.get("at")
                break
        if not delivery_at:
            continue
        ct = _calc_cycle_time_kanban(state_changes)
        if ct is not None and ct >= 0:
            try:
                dt = datetime.fromisoformat(delivery_at.replace("Z", "+00:00"))
                month_key = dt.strftime("%Y-%m")
                monthly_cycle_times.setdefault(month_key, []).append(ct)
            except Exception:
                pass

    cycle_time_by_period = {
        month: {
            "p50": _percentile(sorted(times), 50),
            "p85": _percentile(sorted(times), 85),
            "count": len(times),
        }
        for month, times in sorted(monthly_cycle_times.items())
    }

    return {
        "weekly_throughput": full_throughput,
        "avg_weekly_throughput": avg,
        "trend": trend,
        # Lead time: criação → READY FOR PROD
        "lead_time_p50": _percentile(lead_times, 50),
        "lead_time_p85": _percentile(lead_times, 85),
        "lead_time_by_period": lead_time_by_period,
        # Cycle time: Em andamento → READY FOR PROD (trabalho real)
        "cycle_time_p50": _percentile(cycle_time_values, 50),
        "cycle_time_p85": _percentile(cycle_time_values, 85),
        "avg_cycle_time_days": round(sum(cycle_time_values) / len(cycle_time_values), 1) if cycle_time_values else None,
        "cycle_time_by_period": cycle_time_by_period,
        # Queue time: criação → Em andamento (espera no backlog)
        "queue_time_p50": _percentile(queue_time_values, 50),
        "avg_queue_time_days": round(sum(queue_time_values) / len(queue_time_values), 1) if queue_time_values else None,
        "total_resolved": len(raw_issues),
        "by_priority": by_priority,
        "by_issue_type": by_issue_type,
    }


# ---------------------------------------------------------------------------
# WIP atual (Kanban aging)
# ---------------------------------------------------------------------------

def fetch_kanban_wip():
    """
    Busca issues atualmente em andamento e calcula WIP aging.
    Cada item retorna aging_days e risk_level:
      - 'fresh'    < 7 dias
      - 'normal'   7–14 dias
      - 'at_risk'  15–30 dias
      - 'blocked'  > 30 dias
    Retorna também contagens por nível de risco e a lista de itens bloqueados/em risco.
    """
    jql = (
        f"project = {JIRA_PROJECT_KEY} "
        f'AND statusCategory = "In Progress" '
        f"ORDER BY created ASC"
    )
    fields = ["summary", "status", "created", "updated", "assignee", "priority"]

    raw_issues = _jql_search(jql, fields, max_results=200)

    now = datetime.now(timezone.utc)
    items = []

    for issue in raw_issues:
        f = issue.get("fields", {})
        created_str = f.get("created") or ""

        aging_days = None
        risk_level = "unknown"
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                aging_days = int((now - created_dt).total_seconds() / 86400)
                if aging_days < 7:
                    risk_level = "fresh"
                elif aging_days <= 14:
                    risk_level = "normal"
                elif aging_days <= 30:
                    risk_level = "at_risk"
                else:
                    risk_level = "blocked"
            except Exception:
                pass

        items.append({
            "key": issue.get("key"),
            "summary": f.get("summary"),
            "status": f.get("status", {}).get("name"),
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "aging_days": aging_days,
            "risk_level": risk_level,
            "priority": (f.get("priority") or {}).get("name"),
        })

    blocked = [i for i in items if i["risk_level"] == "blocked"]
    at_risk = [i for i in items if i["risk_level"] == "at_risk"]

    return {
        "items": items,
        "total_wip": len(items),
        "blocked_count": len(blocked),
        "at_risk_count": len(at_risk),
        "blocked": blocked,
        "at_risk": at_risk,
    }


# ---------------------------------------------------------------------------
# Rework breakdown — análise completa de retrabalho por tipo de transição
# ---------------------------------------------------------------------------

_REWORK_JQLS = {
    "review_rejection": 'status CHANGED FROM "In Review" TO "In Progress"',
    "qa_rejection_prog": 'status CHANGED FROM "Ready for Test" TO "In Progress"',
    "qa_rejection_reop": 'status CHANGED FROM "Ready for Test" TO "REOPENED"',
    "review_reopened":  'status CHANGED FROM "In Review" TO "REOPENED"',
    "test_reopened":    'status CHANGED FROM "In Test" TO "REOPENED"',
}


def fetch_rework_breakdown(weeks_back=16):
    """
    Analisa retrabalho por tipo de transição backward no fluxo.
    Para cada padrão (JQL), busca os itens e seus changelogs para contar
    quantas vezes a transição ocorreu por item.

    Retorna:
      - by_type: {label: {total_occurrences, items: [{key, summary, count, assignee}]}}
      - total_items_with_rework: itens únicos com pelo menos 1 retrabalho
      - total_occurrences: soma de todas as ocorrências
    """
    after_clause = f"AFTER -{weeks_back * 7}d"
    all_issue_rework: dict = {}   # key → {summary, assignee, by_type: {}}

    for rw_type, jql_filter in _REWORK_JQLS.items():
        jql = f"project = {JIRA_PROJECT_KEY} AND {jql_filter} {after_clause} ORDER BY updated DESC"
        fields = ["summary", "assignee"]
        issues = _jql_search(jql, fields, max_results=100)

        for issue in issues:
            key = issue.get("key")
            f = issue.get("fields", {})

            if key not in all_issue_rework:
                all_issue_rework[key] = {
                    "summary": f.get("summary"),
                    "assignee": (f.get("assignee") or {}).get("displayName"),
                    "by_type": {},
                }

            # Conta ocorrências via changelog (item pode ter voltado múltiplas vezes)
            state_changes = _get_changelog(key)
            bd = _rework_breakdown(state_changes)

            # Mapeia tipo do JQL → categoria interna
            if "review_rejection" in rw_type:
                cat = "review_rejection"
            elif "qa" in rw_type or "test" in rw_type:
                cat = "qa_rejection"
            else:
                cat = "reopened"

            count = bd.get(cat, 0) or bd.get("reopened", 0) or 1
            prev = all_issue_rework[key]["by_type"].get(cat, 0)
            all_issue_rework[key]["by_type"][cat] = max(prev, count)

    # Agrega por tipo
    by_type: dict = {}
    for key, data in all_issue_rework.items():
        for cat, count in data["by_type"].items():
            if cat not in by_type:
                by_type[cat] = {"total_occurrences": 0, "items": []}
            by_type[cat]["total_occurrences"] += count
            by_type[cat]["items"].append({
                "key": key,
                "summary": data["summary"],
                "count": count,
                "assignee": data["assignee"],
            })

    for cat in by_type:
        by_type[cat]["items"].sort(key=lambda x: -x["count"])

    total_items = len(all_issue_rework)
    total_occurrences = sum(
        sum(d["by_type"].values()) for d in all_issue_rework.values()
    )

    return {
        "weeks_back": weeks_back,
        "total_items_with_rework": total_items,
        "total_occurrences": total_occurrences,
        "by_type": by_type,
    }


# ---------------------------------------------------------------------------
# Work In Stage — itens ativos por etapa com tempo no status atual
# ---------------------------------------------------------------------------

_WORK_STAGES = ["In Progress", "In Review", "Ready for Test", "In Test", "READY FOR PROD"]


def fetch_stage_detail():
    """
    Para cada etapa de trabalho ativa, retorna os itens e há quantos dias
    estão naquele status (via changelog — tempo desde a última entrada no status).
    """
    stages_data = {}

    for stage in _WORK_STAGES:
        jql = f'project = {JIRA_PROJECT_KEY} AND status = "{stage}" ORDER BY updated ASC'
        fields = ["summary", "status", "assignee", "priority", "updated"]
        issues = _jql_search(jql, fields, max_results=50)

        items = []
        now = datetime.now(timezone.utc)

        for issue in issues:
            key = issue.get("key")
            f = issue.get("fields", {})
            state_changes = _get_changelog(key)

            # Encontra a última vez que entrou neste status
            entered_at = None
            for ch in reversed(state_changes):
                if (ch.get("to") or "").strip() == stage:
                    entered_at = ch.get("at")
                    break

            days_in_stage = None
            if entered_at:
                try:
                    dt = datetime.fromisoformat(entered_at.replace("Z", "+00:00"))
                    days_in_stage = int((now - dt).total_seconds() / 86400)
                except Exception:
                    pass

            items.append({
                "key": key,
                "summary": f.get("summary"),
                "assignee": (f.get("assignee") or {}).get("displayName"),
                "priority": (f.get("priority") or {}).get("name"),
                "days_in_stage": days_in_stage,
            })

        items.sort(key=lambda x: x.get("days_in_stage") or 0, reverse=True)

        days_list = [i["days_in_stage"] for i in items if i["days_in_stage"] is not None]
        stages_data[stage] = {
            "items": items,
            "count": len(items),
            "avg_days": round(sum(days_list) / len(days_list), 1) if days_list else None,
            "max_days": max(days_list) if days_list else None,
        }

    return stages_data


# ---------------------------------------------------------------------------
# Retrabalho e deploy lag histórico
# ---------------------------------------------------------------------------

def fetch_rework_and_deploy_metrics(weeks_back=8):
    """
    Para issues resolvidas nas últimas N semanas, busca changelogs e calcula:
      - rework_rate_pct: % de issues que voltaram de teste para dev
      - avg_deploy_lag_days / deploy_lag_p50 / deploy_lag_p85: tempo READY FOR PROD → Concluído
      - rework_items: issues com mais retrabalho
      - deploy_lag_items: issues com maior lag de deploy
    """
    jql = (
        f"project = {JIRA_PROJECT_KEY} "
        f"AND resolved >= -{weeks_back * 7}d "
        f"ORDER BY resolutiondate DESC"
    )
    fields = ["summary", "status", "resolutiondate", "assignee"]
    raw_issues = _jql_search(jql, fields, max_results=100)

    rework_items = []
    deploy_lag_items = []
    deploy_lag_values = []
    cycle_time_values = []
    queue_time_values = []
    total_with_rework = 0
    status_time_accum = {}   # {status: [days, ...]} para média global

    for issue in raw_issues:
        key = issue.get("key")
        f = issue.get("fields", {})
        created_str   = f.get("created") or ""
        resolved_str  = f.get("resolutiondate") or ""
        state_changes = _get_changelog(key)

        rework = _count_rework(state_changes)
        lag    = _calc_deploy_lag(state_changes)
        ct_k   = _calc_cycle_time_kanban(state_changes)
        qt     = _calc_queue_time(created_str, state_changes)
        tis    = _calc_time_in_status(created_str, state_changes, resolved_str)

        if rework > 0:
            total_with_rework += 1
            rework_items.append({
                "key": key,
                "summary": f.get("summary"),
                "rework_count": rework,
                "assignee": (f.get("assignee") or {}).get("displayName"),
            })
        if lag is not None:
            deploy_lag_values.append(lag)
            deploy_lag_items.append({
                "key": key,
                "summary": f.get("summary"),
                "days": lag,
                "assignee": (f.get("assignee") or {}).get("displayName"),
            })
        if ct_k is not None:
            cycle_time_values.append(ct_k)
        if qt is not None:
            queue_time_values.append(qt)
        for status, days in tis.items():
            status_time_accum.setdefault(status, []).append(days)

    deploy_lag_values.sort()
    cycle_time_values.sort()
    queue_time_values.sort()
    deploy_lag_items.sort(key=lambda x: x["days"], reverse=True)
    rework_items.sort(key=lambda x: x["rework_count"], reverse=True)

    avg_time_in_status = {
        s: round(sum(v) / len(v), 1)
        for s, v in status_time_accum.items() if v
    }

    # Agrega rework dos itens semanais (WIP com retrabalho, não só resolved)
    # Esses itens já têm state_changes calculados pelo caller
    # → enriquecimento feito em main.py via jira_data se disponível

    total = len(raw_issues)

    # Lead time full para flow efficiency
    lead_times_full = []
    for issue in raw_issues:
        f = issue.get("fields", {})
        created_str  = f.get("created") or ""
        resolved_str = f.get("resolutiondate") or ""
        if created_str and resolved_str:
            lt = _calc_days(created_str, resolved_str)
            if lt is not None and lt >= 0:
                lead_times_full.append(lt)
    lead_times_full.sort()
    avg_lead = round(sum(lead_times_full) / len(lead_times_full), 1) if lead_times_full else None
    avg_cycle = round(sum(cycle_time_values) / len(cycle_time_values), 1) if cycle_time_values else None
    flow_efficiency = (
        round(avg_cycle / avg_lead * 100, 1)
        if avg_cycle and avg_lead and avg_lead > 0 else None
    )

    return {
        "total_analyzed": total,
        "weeks_back": weeks_back,
        # Rework
        "rework_total": total_with_rework,
        "rework_rate_pct": round(total_with_rework / total * 100, 1) if total else 0,
        "rework_items": rework_items[:10],
        # Deploy lag
        "avg_deploy_lag_days": round(sum(deploy_lag_values) / len(deploy_lag_values), 1) if deploy_lag_values else None,
        "deploy_lag_p50": _percentile(deploy_lag_values, 50),
        "deploy_lag_p85": _percentile(deploy_lag_values, 85),
        "deploy_lag_items": deploy_lag_items[:10],
        "deploy_lag_total": len(deploy_lag_values),
        # Cycle time (Kanban)
        "avg_cycle_time_days": avg_cycle,
        "cycle_time_p50": _percentile(cycle_time_values, 50),
        "cycle_time_p85": _percentile(cycle_time_values, 85),
        # Queue time
        "avg_queue_time_days": round(sum(queue_time_values) / len(queue_time_values), 1) if queue_time_values else None,
        "queue_time_p50": _percentile(queue_time_values, 50),
        # Flow efficiency
        "avg_lead_time_days": avg_lead,
        "flow_efficiency_pct": flow_efficiency,
        # Time in status
        "avg_time_in_status": avg_time_in_status,
    }


if __name__ == "__main__":
    import json, sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=== Issues da semana ===")
    weekly = fetch_weekly_jira_issues()
    finalizadas = [i for i in weekly if i["status_category"] == "done"]
    print(f"Finalizadas: {len(finalizadas)}, Total com movimentação: {len(weekly)}")
    for i in finalizadas:
        print(f"  [{i['key']}] {i['summary']} | ciclo: {i['cycle_time_days']}d | mudanças: {len(i['state_changes'])}")

    print("\n=== Velocity (4 meses) ===")
    velocity = fetch_jira_velocity_history()
    print(f"Total resolvidas: {velocity['total_resolved']} | média/semana: {velocity['avg_weekly_throughput']} | tendência: {velocity['trend']}")
    print(f"Lead time p50: {velocity['lead_time_p50']}d | p85: {velocity['lead_time_p85']}d")

    print("\n=== WIP atual ===")
    wip = fetch_kanban_wip()
    print(f"Total WIP: {wip['total_wip']} | bloqueadas: {wip['blocked_count']} | em risco: {wip['at_risk_count']}")
    for i in wip["blocked"]:
        print(f"  [BLOQUEADO] [{i['key']}] {i['summary']} | {i['aging_days']}d | {i['assignee']}")
    for i in wip["at_risk"]:
        print(f"  [EM RISCO]  [{i['key']}] {i['summary']} | {i['aging_days']}d | {i['assignee']}")
