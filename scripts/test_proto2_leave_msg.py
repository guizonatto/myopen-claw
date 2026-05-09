"""
Teste Protocolo 2 — Cenário: sem atendimento humano agora, chatbot oferece deixar mensagem.
"""
import json, subprocess

PROXY = "http://llm-metrics-proxy:8080/openclaw/v1/chat/completions"
TOKEN = "usage-router-local"
MODELS = ["mistral/mistral-large-latest", "mistral/mistral-medium-2508"]


def load(path):
    return open(path).read()


qual_agents = load("/root/.openclaw/workspace-zind-crm-qualifier/AGENTS.md")
qual_soul   = load("/root/.openclaw/workspace-zind-crm-qualifier/SOUL.md")
cards       = load("/opt/openclaw-bootstrap/workspace/skills/crm/library/battlecards.json")
rules       = load("/opt/openclaw-bootstrap/workspace/skills/crm/library/human_rules.json")

SYSTEM = (
    f"{qual_agents}\n\n---\nSOUL:\n{qual_soul}\n\n"
    f"---\nBATTLECARDS:\n{cards}\n\n---\nHUMAN_RULES:\n{rules}\n\n"
    "Seu nome é RAFA. Voce representa EXCLUSIVAMENTE a Zind (zind.pro)."
)


def call(user_msg):
    for model in MODELS:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", PROXY,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {TOKEN}",
             "-d", json.dumps({
                 "model": model,
                 "messages": [
                     {"role": "system", "content": SYSTEM},
                     {"role": "user",   "content": user_msg}
                 ],
                 "max_tokens": 200
             })],
            capture_output=True, text=True, timeout=40
        )
        try:
            d = json.loads(r.stdout)
            if "choices" in d:
                return d["choices"][0]["message"]["content"].strip(), model
        except Exception:
            pass
    return "[FALHOU]", "?"


def show(label, text, model=""):
    tag = f"[{model.split('/')[-1]}]" if model else ""
    flag = f" ⚠️ {len(text)}ch > 180" if len(text) > 180 else f" ✅ {len(text)}ch"
    print(f"\n{label}{flag}")
    print(f"  → \"{text}\"")


print("=" * 60)
print("PROTOCOLO 2 — Sem atendente disponível / Deixar mensagem")
print("=" * 60)

# ── Etapa 1: bypass enviado pelo agente ─────────────────────────────────────
show("[Agente já enviou]", "Falar com atendente.")

# ── Bot responde: ninguém disponível, mas pode deixar mensagem ───────────────
no_human = (
    "No momento não há atendentes disponíveis. "
    "Para deixar uma mensagem, responda com o texto que deseja registrar "
    "e entraremos em contato em breve. "
    "Ou digite MENU para voltar ao início."
)
print(f"\n[Bot — sem atendente]\n  Bot: \"{no_human}\"")

# ── O que o qualifier decide fazer? ─────────────────────────────────────────
msg_no_human = (
    "LEAD_ID: sim-sindico-sp\nINTENT: bot_gatekeeper\nSTAGE: lead\n"
    f"MENSAGEM_DO_LEAD: {no_human}\n\n"
    "CONTEXTO: após enviar 'Falar com atendente.', o bot informou que não há "
    "atendentes disponíveis no momento e oferece a opção de deixar uma mensagem "
    "para ser vista depois.\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp a enviar."
)
resp1, m1 = call(msg_no_human)
show("[Qualifier decide]", resp1, m1)

# ── Bot confirma que registrou a mensagem ────────────────────────────────────
bot_confirma = (
    "Mensagem registrada! Nossa equipe entrará em contato em até 24h. "
    "Agradecemos o contato com a Administradora Central."
)
print(f"\n[Bot confirma registro]\n  Bot: \"{bot_confirma}\"")

# ── Segunda interação: o que o agente faz após confirmação? ──────────────────
msg_after = (
    "LEAD_ID: sim-sindico-sp\nINTENT: bot_gatekeeper\nSTAGE: lead\n"
    f"MENSAGEM_DO_LEAD: {bot_confirma}\n\n"
    "CONTEXTO: bot confirmou que a mensagem foi registrada e que alguém entrará "
    "em contato. Não há mais ação possível via chatbot neste momento.\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp, ou retorne vazio se não há ação."
)
resp2, m2 = call(msg_after)
show("[Qualifier após confirmação]", resp2, m2)

print("\n" + "=" * 60)
