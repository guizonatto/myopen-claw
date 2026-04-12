"""
Orquestrador da skill github-weekly-summary.
Executa: fetch_github_releases → fetch_jira_issues → generate_summaries → export_to_notion → send_to_discord
Valida variáveis de ambiente, paginação, integração IA e logs claros.
"""
import os
import sys
from fetch_github_releases import fetch_weekly_releases_and_commits
from fetch_jira_issues import fetch_weekly_jira_issues
from generate_summaries import generate_summaries
from export_to_notion import export_to_notion
from send_to_discord import send_to_discord
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "GITHUB_TOKEN", "GITHUB_REPO",
    "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_BASE_URL", "JIRA_PROJECT_KEY",
    "NOTION_TOKEN", "NOTION_DATABASE_ID",
    "DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID"
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
        print(f"[INFO] Releases coletadas: {len(github_data['releases'])}")
        print(f"[INFO] Commits coletados: {len(github_data['commits'])}")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar dados do GitHub: {e}")
        github_data = {"releases": [], "commits": []}
    try:
        print("[INFO] Buscando issues Jira...")
        jira_data = fetch_weekly_jira_issues()
        print(f"[INFO] Issues Jira coletadas: {len(jira_data)}")
    except Exception as e:
        print(f"[ERRO] Falha ao buscar issues Jira: {e}")
        jira_data = []
    try:
        print("[INFO] Gerando resumos com IA...")
        summaries = generate_summaries(github_data, jira_data)
    except Exception as e:
        print(f"[ERRO] Falha ao gerar resumos: {e}")
        summaries = {"erro": str(e), "notion": {"properties": {}, "children": []}}
    try:
        print("[INFO] Exportando para Notion...")
        notion_result = export_to_notion(summaries["notion"])
        print(f"[OK] Página criada no Notion: {notion_result.get('url','(sem url)')}")
    except Exception as e:
        print(f"[ERRO] Falha ao exportar para Notion: {e}")
    try:
        print("[INFO] Enviando resumo para Discord...")
        discord_result = send_to_discord(summaries.get("discord", ""))
        print(f"[OK] Mensagem enviada para Discord: {discord_result.get('id','(sem id)')}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar para Discord: {e}")
    print("[SUCESSO] Pipeline concluída.")

if __name__ == "__main__":
    main()
