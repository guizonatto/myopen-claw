"""
Teste Protocolo 2 — Navegação de chatbot (gatekeeper).
Fluxo:
  Acao 1: cold-contact envia saudação
  Bot responde com menu numérico
  → orquestrador classificaria: bot_gatekeeper → qualifier
  Etapa 1: qualifier envia bypass exato
  Bot ainda responde como bot (fallback)
  Etapa 2: qualifier detecta humano assumiu e envia pergunta do gatekeeper
"""
import json, subprocess, sys

PROXY = "http://llm-metrics-proxy:8080/openclaw/v1/chat/completions"
TOKEN = "usage-router-local"
MODEL_FALLBACK = ["mistral/mistral-large-latest", "mistral/mistral-medium-2508"]

def load(path):
    return open(path).read()

# Load agent configs
cold_agents  = load("/root/.openclaw/workspace-zind-crm-cold-contact/AGENTS.md")
cold_soul    = load("/root/.openclaw/workspace-zind-crm-cold-contact/SOUL.md")
cold_id      = load("/root/.openclaw/workspace-zind-crm-cold-contact/IDENTITY.md")
qual_agents  = load("/root/.openclaw/workspace-zind-crm-qualifier/AGENTS.md")
qual_soul    = load("/root/.openclaw/workspace-zind-crm-qualifier/SOUL.md")
cards        = load("/opt/openclaw-bootstrap/workspace/skills/crm/library/battlecards.json")
rules        = load("/opt/openclaw-bootstrap/workspace/skills/crm/library/human_rules.json")

SYSTEM_COLD = (
    f"{cold_agents}\n\n---\nSOUL:\n{cold_soul}\n\n---\nIDENTITY:\n{cold_id}\n\n"
    f"---\nBATTLECARDS:\n{cards}\n\n---\nHUMAN_RULES:\n{rules}\n\n"
    "Seu nome é RAFA. Voce representa EXCLUSIVAMENTE a Zind (zind.pro)."
)

SYSTEM_QUAL = (
    f"{qual_agents}\n\n---\nSOUL:\n{qual_soul}\n\n"
    f"---\nBATTLECARDS:\n{cards}\n\n---\nHUMAN_RULES:\n{rules}\n\n"
    "Seu nome é RAFA. Voce representa EXCLUSIVAMENTE a Zind (zind.pro)."
)


def call(system, user_msg):
    payload = json.dumps({
        "model": MODEL_FALLBACK[0],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg}
        ],
        "max_tokens": 150
    })
    for model in MODEL_FALLBACK:
        p = json.loads(payload)
        p["model"] = model
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", PROXY,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {TOKEN}",
             "-d", json.dumps(p)],
            capture_output=True, text=True, timeout=40
        )
        try:
            d = json.loads(r.stdout)
            if "choices" in d:
                return d["choices"][0]["message"]["content"].strip(), model
        except Exception:
            pass
    return "[FALHOU]", "?"


print("=" * 60)
print("PROTOCOLO 2 — Navegação Chatbot / Gatekeeper")
print("=" * 60)

# ── Ação 1: cold-contact abre conversa ──────────────────────────────────────
msg_a1 = (
    "LEAD_ID: sim-sindico-sp\nINTENT: greeting\nSTAGE: lead\n"
    "DOR: retrabalho em follow-up\nSINAL: Google — busca por síndico profissional SP\n"
    "FIT: alta\nTOM: direto\nMENSAGEM_DO_LEAD: (inicio da conversa)\n\n"
    "CONTEXTO PRE-CARREGADO: nome: desconhecido, cidade: sao_paulo, "
    "interaction_history: 0 eventos — Acao 1\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp."
)
resp_a1, model_a1 = call(SYSTEM_COLD, msg_a1)
print(f"\n[Cold-contact Acao 1 → Lead]\n  Agente: \"{resp_a1}\" ({len(resp_a1)}ch)")

# ── Bot responde com menu ────────────────────────────────────────────────────
chatbot_menu = (
    "Olá! Obrigado por entrar em contato com a Administradora Central. "
    "Por favor, selecione uma opção:\n"
    "1️⃣ Financeiro\n2️⃣ Manutenção\n3️⃣ Assembleias\n4️⃣ Outros\n\n"
    "Digite o número da opção desejada."
)
print(f"\n[Chatbot responde]\n  Bot: \"{chatbot_menu[:80]}...\"")
print("\n  → Orquestrador classifica: bot_gatekeeper → zind-crm-qualifier")

# ── Qualifier: Etapa 1 — bypass do menu ─────────────────────────────────────
msg_bypass = (
    "LEAD_ID: sim-sindico-sp\nINTENT: bot_gatekeeper\nSTAGE: lead\n"
    f"DOR: retrabalho em follow-up\nSINAL: Google\nFIT: alta\nTOM: direto\n"
    f"MENSAGEM_DO_LEAD: {chatbot_menu}\n\n"
    "CONTEXTO: resposta parece menu de chatbot numerado. "
    "Aplicar Etapa 1 do Protocolo 2.\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp."
)
resp_bypass, model_b = call(SYSTEM_QUAL, msg_bypass)
print(f"\n[Qualifier Etapa 1 — Bypass]\n  Agente: \"{resp_bypass}\" ({len(resp_bypass)}ch)")

bypass_ok = resp_bypass.strip().lower() in {"falar com atendente.", "falar com humano.", "falar com atendente", "falar com humano"}
print(f"  Script canônico: {'✅' if bypass_ok else '⚠️  esperado: Falar com atendente.'}")

# ── Bot ainda responde como bot (fallback necessário) ────────────────────────
bot_fallback = "Por favor, selecione uma das opções: 1 2 3 4"
print(f"\n[Chatbot ainda responde]\n  Bot: \"{bot_fallback}\"")

msg_fallback = (
    "LEAD_ID: sim-sindico-sp\nINTENT: bot_gatekeeper\nSTAGE: lead\n"
    f"MENSAGEM_DO_LEAD: {bot_fallback}\n\n"
    "CONTEXTO: segunda tentativa de bypass — bot ainda respondendo. "
    "Aplicar fallback do Protocolo 2 Etapa 1.\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp."
)
resp_fallback, _ = call(SYSTEM_QUAL, msg_fallback)
print(f"\n[Qualifier Etapa 1 Fallback]\n  Agente: \"{resp_fallback}\" ({len(resp_fallback)}ch)")

# ── Humano assume o chat ─────────────────────────────────────────────────────
humano_responde = "Olá! Aqui é a Ana, posso ajudar?"
print(f"\n[Humano assume o chat]\n  Ana: \"{humano_responde}\"")
print("  → Sinal de humano detectado: mudança de tom, resposta fora do padrão de menu")

msg_gatekeeper = (
    "LEAD_ID: sim-sindico-sp\nINTENT: bot_gatekeeper\nSTAGE: lead\n"
    f"MENSAGEM_DO_LEAD: {humano_responde}\n\n"
    "CONTEXTO: humano assumiu o chat (Ana, atendente). "
    "Aplicar Etapa 2 do Protocolo 2 — pergunta ao gatekeeper.\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp."
)
resp_gk, model_gk = call(SYSTEM_QUAL, msg_gatekeeper)
print(f"\n[Qualifier Etapa 2 — Gatekeeper]\n  Agente: \"{resp_gk}\" ({len(resp_gk)}ch)")

gk_ok = "melhor pessoa" in resp_gk.lower() or "sistema de gestão" in resp_gk.lower() or "síndico" in resp_gk.lower()
print(f"  Pergunta correta ao gatekeeper: {'✅' if gk_ok else '⚠️'}")

print("\n" + "=" * 60)
print("RESULTADO:")
print(f"  Acao 1 (cold-contact): {'✅' if len(resp_a1) <= 180 else '⚠️'} {len(resp_a1)}ch")
print(f"  Etapa 1 bypass:        {'✅' if bypass_ok else '⚠️'}")
print(f"  Etapa 2 gatekeeper:    {'✅' if gk_ok else '⚠️'}")
print("=" * 60)
