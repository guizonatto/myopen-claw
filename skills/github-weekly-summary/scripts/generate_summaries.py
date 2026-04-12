"""
Gera resumos semanais (FAQ, CEO, Discord, e-mail, RAG, Notion) a partir dos dados de releases GitHub e issues Jira.
Sugestão: integrar com API de IA para sumarização real (ex: OpenAI, Claude, Gemini) OU chamar uma skill de sumarização já pronta.
O retorno precisa ser compatível com export_to_notion (deve conter 'properties' e 'children' em summaries['notion']).
"""
import os
import json

def generate_summaries(github_data, jira_data):
    # Exemplo de integração fictícia com IA
    import openai
    try:
        # Substitua pelo modelo correto
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Resuma releases e issues para FAQ, CEO, Discord, Notion, etc."},
                {"role": "user", "content": f"GitHub: {github_data}\nJira: {jira_data}"}
            ],
            temperature=0.3,
            max_tokens=2048
        )
        content = response.choices[0].message.content
        try:
            summaries = json.loads(content)
        except json.JSONDecodeError as je:
            print(f"[IA] JSON inválido: {je}\nConteúdo bruto:\n{content}")
            summaries = {"erro": "JSON inválido da IA", "raw": content}
    except Exception as e:
        print(f"[IA] Erro ao gerar resumo: {e}")
        summaries = {"erro": str(e)}
    # Garante estrutura mínima
    if "notion" not in summaries:
        summaries["notion"] = {"properties": {}, "children": []}
    return summaries

import sys

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python generate_summaries.py <github_data.json> <jira_data.json>")
        sys.exit(1)
    github_path = sys.argv[1]
    jira_path = sys.argv[2]
    with open(github_path) as f:
        github_data = json.load(f)
    with open(jira_path) as f:
        jira_data = json.load(f)
    print(generate_summaries(github_data, jira_data))
