import os
import requests
from dotenv import load_dotenv

# =====================================================================
# 1. CONFIGURAÇÕES
# =====================================================================
load_dotenv()

JIRA_TOKEN = os.environ.get('JIRA_TOKEN') 
JIRA_URL = os.environ.get('JIRA_BASE_URL', 'https://zind-team.atlassian.net').rstrip('/')
JIRA_EMAIL = os.environ.get('JIRA_EMAIL')

def audit_jira():
    print(f"🕵️ Investigando o usuário: {JIRA_EMAIL}")
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    headers = {"Accept": "application/json"}

    # --- PASSO 1: QUEM SOU EU? ---
    # Verifica se o Token pertence mesmo ao e-mail configurado
    print("\n1️⃣ Verificando Identidade...")
    try:
        res_me = requests.get(f"{JIRA_URL}/rest/api/3/myself", auth=auth, headers=headers)
        if res_me.status_code == 200:
            user_data = res_me.json()
            print(f"✅ Identificado como: {user_data.get('displayName')} (ID: {user_data.get('accountId')})")
        else:
            print(f"❌ Erro ao identificar usuário: {res_me.status_code}")
            return
    except Exception as e:
        print(f"❌ Falha de conexão: {e}")
        return

    # --- PASSO 2: QUAIS PROJETOS EU ENXERGO? ---
    # Se o projeto ZIN não aparecer aqui, o Token não tem acesso a ele
    print("\n2️⃣ Listando projetos visíveis para este Token...")
    try:
        res_proj = requests.get(f"{JIRA_URL}/rest/api/3/project", auth=auth, headers=headers)
        if res_proj.status_code == 200:
            projects = res_proj.json()
            if not projects:
                print("⚠️ O Token não enxerga NENHUM projeto. (Problema de Permissão)")
            else:
                for p in projects:
                    print(f"   - Projeto: {p.get('name')} | Key: {p.get('key')}")
        else:
            print(f"❌ Erro ao listar projetos: {res_proj.status_code}")
    except Exception as e:
        print(f"❌ Falha ao listar projetos: {e}")

    # --- PASSO 3: TOTAL DE ISSUES NO JIRA INTEIRO ---
    print("\n3️⃣ Buscando total de issues acessíveis no domínio...")
    try:
        search_url = f"{JIRA_URL}/rest/api/3/search/jql"
        # JQL vazio traz tudo o que o usuário tem permissão de ver
        res_search = requests.post(
            search_url, 
            auth=auth, 
            json={"jql": "", "maxResults": 1}, 
            headers={"Content-Type": "application/json"}
        )
        if res_search.status_code == 200:
            total = res_search.json().get('total', 0)
            print(f"📊 Total de issues visíveis para você: {total}")
        else:
            print(f"❌ Erro na busca global: {res_search.status_code}")
    except Exception as e:
        print(f"❌ Falha na busca: {e}")

if __name__ == "__main__":
    audit_jira()