import json, subprocess, sys

PROXY = "http://llm-metrics-proxy:8080/openclaw/v1/chat/completions"
TOKEN = "usage-router-local"

agents_md = open("/root/.openclaw/workspace-zind-crm-cold-contact/AGENTS.md").read()
soul_md   = open("/root/.openclaw/workspace-zind-crm-cold-contact/SOUL.md").read()
cards     = open("/opt/openclaw-bootstrap/workspace/skills/crm/library/battlecards.json").read()
rules     = open("/opt/openclaw-bootstrap/workspace/skills/crm/library/human_rules.json").read()

SYSTEM = (
    f"{agents_md}\n\n---\nSOUL:\n{soul_md}\n\n"
    f"---\nBATTLECARDS:\n{cards}\n\n"
    f"---\nHUMAN_RULES:\n{rules}\n\n"
    "Voce representa EXCLUSIVAMENTE a Zind (zind.pro). Nunca mencione concorrentes."
)

def call(model, user_msg):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
        "max_tokens": 200
    })
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", PROXY,
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Bearer {TOKEN}",
         "-d", payload],
        capture_output=True, text=True, timeout=40
    )
    d = json.loads(r.stdout)
    if "choices" in d:
        return d["choices"][0]["message"]["content"].strip()
    return f"[ERRO] {d.get('message','?')[:80]}"

def run(acao, history, intent, last_msg):
    user_msg = (
        f"LEAD_ID: sim-joao-sp\nINTENT: {intent}\nSTAGE: lead\n"
        f"DOR: retrabalho em follow-up e pagamento\nSINAL: grupo de sindicos de SP\n"
        f"FIT: alta\nTOM: direto e casual\nMENSAGEM_DO_LEAD: {last_msg}\n\n"
        f"CONTEXTO PRE-CARREGADO:\nnome: Joao\nsetor: gestao condominial\ncidade: sao_paulo\n"
        f"interaction_history: {history} eventos outbound cold-contact — executar Acao {acao}\n\n"
        "Retorne APENAS o texto da mensagem WhatsApp, sem prefixo, sem explicacao."
    )
    for model in ["mistral/mistral-large-latest", "mistral/mistral-medium-2508"]:
        t = call(model, user_msg)
        if not t.startswith("[ERRO]"):
            return t, model
    return "[FALHOU]", "?"

for acao, history, intent, last_msg in [
    (3, 2, "interest_uncertain", "Uso o Excel pra tudo ainda."),
    (4, 3, "interest_uncertain", "Interessante. Como funciona?"),
]:
    text, model = run(acao, history, intent, last_msg)
    flags = ["LONGO"] if len(text) > 220 else []
    if "condoseg" in text.lower(): flags.append("CONDOSEG")
    print(f"\n--- Acao {acao} [{model}] ---")
    print(f"Lead: \"{last_msg}\"")
    print(f"Agente: \"{text}\"")
    print(f"chars={len(text)} | {'[FAIL] ' + ' | '.join(flags) if flags else '[OK]'}")
