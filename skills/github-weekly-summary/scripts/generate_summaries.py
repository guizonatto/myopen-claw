"""
Gera resumos semanais (FAQ, CEO, Discord, e-mail, RAG, Kanban, Notion) a partir dos dados
de releases GitHub, issues Jira, velocity histórico e WIP atual.
Usa o model router local (usage-router → devstral-medium-latest).
"""
import os
import json
from openai import OpenAI

SYSTEM_PROMPT = """\
Você é um assistente especialista em relatórios de engenharia de software.
Receberá dados de GitHub releases/commits, issues Jira da semana, velocity dos últimos 4 meses e WIP atual do Kanban.
Retorne SOMENTE um JSON válido com as chaves abaixo — sem markdown, sem explicação, sem texto fora do JSON.

Chaves obrigatórias do JSON:
- "faq_vendas"    : string — FAQ para time de vendas/suporte (o que mudou, impacto no cliente)
- "faq_usuario"   : string — FAQ para usuário final (o que é, como usar, benefícios)
- "ceo"           : string — Resumo executivo com entregas, métricas, riscos e próximos passos
- "discord"       : string — Mensagem curta para Discord com emojis (máx 1800 chars)
- "email"         : string — E-mail formatado com assunto e corpo
- "rag"           : string — Texto estruturado para indexação IA com todas as funcionalidades
- "kanban"        : objeto com:
    - "highlights"        : string — 2-3 frases sobre o estado atual do board
    - "velocity_trend"    : string — análise da tendência de velocity (acelerando/estável/desacelerando + contexto)
    - "lead_time_insight" : string — interpretação dos p50/p85 e o que significam para o time
    - "wip_alerts"        : string — alertas de itens bloqueados/em risco com nomes e dias parados
    - "recommendations"   : string — 1-3 ações concretas para melhorar o fluxo
- "notion"        : objeto com:
    - "properties": objeto com title (string), date (string YYYY-MM-DD), tags (array de strings)
    - "children"  : array de blocos Notion (paragraph, heading_2, bulleted_list_item, etc.)

Regras:
- Se não houver releases GitHub, diga "Nenhuma release publicada esta semana".
- Para o "discord", nunca use tabelas markdown — use listas com emojis.
- Para "ceo", inclua sempre a seção de Kanban Metrics com velocity, lead time e WIP.
- Para "kanban.wip_alerts", liste apenas itens com risk_level 'blocked' ou 'at_risk' pelo nome e dias parados.
- Para "kanban.velocity_trend", compare a média das últimas 4 semanas com a média geral do período.
"""


def generate_summaries(github_data, jira_data, velocity_data=None, wip_data=None):
    client = OpenAI(
        base_url=(
            os.environ.get("MODEL_USAGE_PROXY_ROOT", "http://llm-metrics-proxy:8080").rstrip("/")
            + "/openclaw/v1"
        ),
        api_key=os.environ.get("MODEL_USAGE_PROXY_TOKEN", "usage-router-local"),
    )

    user_parts = [
        f"## GitHub (semana)\n{json.dumps(github_data, ensure_ascii=False)}",
        f"## Jira issues (semana)\n{json.dumps(jira_data, ensure_ascii=False)}",
    ]
    if velocity_data:
        user_parts.append(f"## Velocity histórico (4 meses)\n{json.dumps(velocity_data, ensure_ascii=False)}")
    if wip_data:
        user_parts.append(f"## WIP atual (Kanban)\n{json.dumps(wip_data, ensure_ascii=False)}")

    response = client.chat.completions.create(
        model="devstral-medium-latest",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ],
        temperature=0.3,
        max_tokens=4096,
    )

    content = response.choices[0].message.content or ""
    # Strip possível markdown fence caso o modelo inclua mesmo com instrução
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rsplit("```", 1)[0].strip()

    try:
        summaries = json.loads(content)
    except json.JSONDecodeError as je:
        print(f"[IA] JSON inválido: {je}\nConteúdo bruto:\n{content}")
        summaries = {"erro": "JSON inválido da IA", "raw": content}

    summaries.setdefault("notion", {"properties": {}, "children": []})
    summaries.setdefault("kanban", {})
    return summaries


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Uso: python generate_summaries.py <github_data.json> <jira_data.json> [velocity.json] [wip.json]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        github_data = json.load(f)
    with open(sys.argv[2]) as f:
        jira_data = json.load(f)
    velocity_data = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    wip_data = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else None

    result = generate_summaries(github_data, jira_data, velocity_data, wip_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
