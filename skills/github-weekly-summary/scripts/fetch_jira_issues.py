import os
import requests
from dotenv import load_dotenv

# =====================================================================
# 1. CONFIGURAÇÕES
# =====================================================================
load_dotenv()

JIRA_TOKEN = os.environ.get('JIRA_TESTE_TOKEN') or os.environ.get('JIRA_TOKEN')
JIRA_URL = "https://zind-team.atlassian.net"
JIRA_EMAIL = "guizonatto@gmail.com"
BOARD_ID = "1"

def fetch_filtered_board_report():
    print(f"📊 Gerando Relatório Dinâmico - Board {BOARD_ID}")
    
    # O SEGREDO: Filtramos direto na fonte para não estourar o limite de issues
    # updated >= -7d : Traz tudo mexido na última semana
    # order by updated DESC : Traz o mais recente primeiro
    jql_filter = "updated >= -7d ORDER BY updated DESC"
    
    url = f"{JIRA_URL}/rest/agile/1.0/board/{BOARD_ID}/issue"
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    
    params = {
        "jql": jql_filter,
        "maxResults": 100, # Agora esses 100 serão os 100 mais recentes
        "fields": "summary,status,updated,comment,assignee,statuscategorychangedate",
        "expand": "comment"
    }

    try:
        response = requests.get(url, params=params, auth=auth)
        if response.status_code != 200:
            print(f"❌ Erro na API: {response.status_code}")
            return

        data = response.json()
        issues = data.get("issues", [])
        
        print(f"✨ Filtro aplicado: {jql_filter}")
        print(f"✅ {len(issues)} issues encontradas com movimentação recente.\n")

        # Categorias para o relatório
        finalizadas = []
        em_andamento = []
        comentarios = []

        for issue in issues:
            f = issue.get("fields", {})
            key = issue.get("key")
            summary = f.get("summary")
            status = f.get("status", {}).get("name")
            category = f.get("status", {}).get("statusCategory", {}).get("key")
            
            item = f"• [{key}] {summary} ({status})"

            if category == "done":
                finalizadas.append(item)
            else:
                em_andamento.append(item)

            # Pegar comentários da semana
            all_comments = f.get("comment", {}).get("comments", [])
            if all_comments:
                ultimo = all_comments[-1] # Pega o comentário mais recente
                comentarios.append(f"💬 [{key}] {ultimo.get('author', {}).get('displayName')}: {ultimo.get('body')[:80]}...")

        # --- OUTPUT FORMATADO ---

        print("--- 🏆 ENTREGUE (Últimos 7 dias) ---")
        print("\n".join(finalizadas) if finalizadas else "Sem entregas registradas.")

        print("\n--- 🚧 EM ANDAMENTO / READY FOR TEST ---")
        print("\n".join(em_andamento) if em_andamento else "Sem tickets em andamento.")

        print("\n--- 🗣️ ÚLTIMAS DISCUSSÕES ---")
        print("\n".join(comentarios[:10]) if comentarios else "Nenhum comentário novo.")

    except Exception as e:
        print(f"❌ Falha técnica: {e}")

if __name__ == "__main__":
    fetch_filtered_board_report()