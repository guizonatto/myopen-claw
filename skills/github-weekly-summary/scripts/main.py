"""
Orquestrador da skill github-weekly-summary.
Executa: fetch_github_releases → fetch_jira_issues → fetch_velocity → fetch_wip
      → generate_summaries → export_to_notion → send_to_discord
"""
import os
import sys
from datetime import datetime, timezone
from fetch_github_releases import fetch_weekly_releases_and_commits
from fetch_jira_issues import (
    fetch_weekly_jira_issues,
    fetch_jira_velocity_history,
    fetch_kanban_wip,
    fetch_rework_and_deploy_metrics,
    fetch_rework_breakdown,
    fetch_stage_detail,
)
from generate_summaries import generate_summaries
from charts import (
    render_velocity_ascii,
    render_lead_time_ascii,
    render_lead_time_trend_ascii,
    render_cycle_time_kanban_ascii,
    render_cycle_time_trend_ascii,
    render_stage_count_ascii,
    render_stage_detail_ascii,
    render_wip_per_person_ascii,
    render_wip_ascii,
    render_wip_list,
    render_delivered_list,
    render_state_changes_list,
    render_flow_efficiency_ascii,
    render_time_in_status_ascii,
    render_deploy_lag_ascii,
    render_rework_ascii,
    render_rework_breakdown_ascii,
)
from export_to_notion import export_to_notion
from send_to_discord import send_to_discord
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "GITHUB_TOKEN", "GITHUB_REPO",
    "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_BASE_URL", "JIRA_PROJECT_KEY",
    "NOTION_TOKEN", "NOTION_DATABASE_ID",
    "DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID",
]


def check_env():
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        print(f"[ERRO] Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)


def main():
    check_env()

    try:
        print("[INFO] Buscando releases e commits do GitHub...")
        github_data = fetch_weekly_releases_and_commits()
        print(f"[INFO] Releases: {len(github_data['releases'])} | Commits: {len(github_data['commits'])}")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados do GitHub: {e}")
        github_data = {"releases": [], "commits": []}

    try:
        print("[INFO] Buscando issues Jira da semana...")
        jira_data = fetch_weekly_jira_issues()
        finalizadas = sum(1 for i in jira_data if i.get("status_category") == "done")
        print(f"[INFO] Issues: {len(jira_data)} com movimentação | {finalizadas} finalizadas")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar issues Jira: {e}")
        jira_data = []

    try:
        print("[INFO] Buscando velocity histórico (4 meses)...")
        velocity_data = fetch_jira_velocity_history()
        print(
            f"[INFO] Velocity: {velocity_data['total_resolved']} resolvidas | "
            f"média {velocity_data['avg_weekly_throughput']}/semana | "
            f"tendência: {velocity_data['trend']}"
        )
    except Exception as e:
        print(f"[ERRO] Falha ao buscar velocity: {e}")
        velocity_data = {}

    try:
        print("[INFO] Analisando retrabalho por tipo de transição (16 semanas)...")
        rework_breakdown_data = fetch_rework_breakdown(weeks_back=16)
        print(
            f"[INFO] Rework breakdown: {rework_breakdown_data['total_items_with_rework']} itens "
            f"| {rework_breakdown_data['total_occurrences']} ocorrências"
        )
    except Exception as e:
        print(f"[ERRO] Falha ao buscar rework breakdown: {e}")
        rework_breakdown_data = {}

    try:
        print("[INFO] Calculando retrabalho e deploy lag (8 semanas)...")
        rework_data = fetch_rework_and_deploy_metrics(weeks_back=8)
        print(
            f"[INFO] Rework: {rework_data['rework_rate_pct']}% ({rework_data['rework_total']}/{rework_data['total_analyzed']}) | "
            f"Deploy lag avg: {rework_data.get('avg_deploy_lag_days')}d"
        )
    except Exception as e:
        print(f"[ERRO] Falha ao calcular rework/deploy lag: {e}")
        rework_data = {}

    try:
        print("[INFO] Buscando detalhe por etapa (In Progress / In Review / ...)...")
        stage_data = fetch_stage_detail()
        for stage, d in stage_data.items():
            print(f"  {stage}: {d['count']} itens | avg: {d.get('avg_days')}d | max: {d.get('max_days')}d")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar stage detail: {e}")
        stage_data = {}

    try:
        print("[INFO] Buscando WIP atual (Kanban)...")
        wip_data = fetch_kanban_wip()
        print(
            f"[INFO] WIP: {wip_data['total_wip']} em andamento | "
            f"{wip_data['blocked_count']} bloqueadas | "
            f"{wip_data['at_risk_count']} em risco"
        )
    except Exception as e:
        print(f"[ERRO] Falha ao buscar WIP: {e}")
        wip_data = {}

    try:
        print("[INFO] Gerando resumos com IA...")
        summaries = generate_summaries(github_data, jira_data, velocity_data, wip_data)
    except Exception as e:
        print(f"[ERRO] Falha ao gerar resumos: {e}")
        summaries = {"erro": str(e), "notion": {"properties": {}, "children": []}}

    try:
        print("[INFO] Exportando para Notion...")
        notion_result = export_to_notion(summaries["notion"])
        print(f"[OK] Página criada no Notion: {notion_result.get('url', '(sem url)')}")
    except Exception as e:
        print(f"[ERRO] Falha ao exportar para Notion: {e}")

    try:
        print("[INFO] Enviando resumo para Discord...")
        parts = []

        narrative = summaries.get("discord", "").strip()
        if narrative:
            parts.append(narrative)

        if velocity_data:
            parts.append(render_velocity_ascii(velocity_data))
            parts.append(render_lead_time_trend_ascii(velocity_data))
            parts.append(render_lead_time_ascii(velocity_data))

        if wip_data:
            parts.append(render_wip_ascii(wip_data))
            parts.append(render_wip_list(wip_data))

        if velocity_data:
            parts.append(render_cycle_time_kanban_ascii(velocity_data))
            parts.append(render_cycle_time_trend_ascii(velocity_data))

        if stage_data:
            parts.append(render_stage_count_ascii(stage_data))
            parts.append(render_wip_per_person_ascii(stage_data))
            parts.append(render_stage_detail_ascii(stage_data))

        if rework_data:
            # Flow efficiency usa cycle time do velocity (mais completo) + lead time do rework
            flow_input = dict(rework_data)
            flow_input["avg_cycle_time_days"] = velocity_data.get("avg_cycle_time_days")
            flow_input["avg_queue_time_days"] = velocity_data.get("avg_queue_time_days")
            flow_input["avg_lead_time_days"] = velocity_data.get("lead_time_p50")
            parts.append(render_flow_efficiency_ascii(flow_input))
            parts.append(render_time_in_status_ascii(rework_data))
            parts.append(render_deploy_lag_ascii(rework_data))

            # Rework: combina dados históricos (resolved) com dados semanais (WIP)
            weekly_rework = [i for i in jira_data if i.get("rework_count", 0) > 0]
            if weekly_rework and rework_data.get("rework_total", 0) == 0:
                # Rework encontrado apenas nos itens semanais (WIP ainda aberto)
                rework_data = dict(rework_data)
                rework_data["rework_total"] = len(weekly_rework)
                rework_data["rework_rate_pct"] = round(
                    len(weekly_rework) / max(rework_data["total_analyzed"], 1) * 100, 1
                )
                rework_data["rework_items"] = [
                    {"key": i["key"], "summary": i["summary"],
                     "rework_count": i["rework_count"], "assignee": i.get("assignee")}
                    for i in sorted(weekly_rework, key=lambda x: -x["rework_count"])
                ]
            parts.append(render_rework_ascii(rework_data))

        if rework_breakdown_data:
            parts.append(render_rework_breakdown_ascii(rework_breakdown_data))

        parts.append(render_delivered_list(jira_data))
        parts.append(render_state_changes_list(jira_data))

        now = datetime.now(timezone.utc)
        week_num = now.strftime("%V")
        date_str = now.strftime("%Y-%m-%d")
        thread_title = f"Weekly Report — W{week_num} {date_str}"

        weekly_channel_id = os.getenv("GITHUB_WEEKLY_DISCORD_CHANNEL_ID") or os.getenv("DISCORD_CHANNEL_ID")
        discord_result = send_to_discord(
            [p for p in parts if p and p.strip()],
            channel_id=weekly_channel_id,
            thread_title=thread_title,
        )
        print(f"[OK] Mensagens enviadas para Discord: última id={discord_result.get('id', '(sem id)')}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar para Discord: {e}")

    print("[SUCESSO] Pipeline concluída.")


if __name__ == "__main__":
    main()
