"""Teste fluxo gatekeeper → indicação → protocolo indicação."""
import json, subprocess

PROXY = "http://llm-metrics-proxy:8080/openclaw/v1/chat/completions"
TOKEN = "usage-router-local"
MODELS = [
    "mistral/mistral-medium-2508",
    "mistral/mistral-large-latest",
    "mistral/mistral-small-latest",
]


def load(path):
    return open(path).read()


def build_system(agent):
    agents_md = load(f"/root/.openclaw/workspace-zind-crm-{agent}/AGENTS.md")
    soul_md   = load(f"/root/.openclaw/workspace-zind-crm-{agent}/SOUL.md")
    cards     = load("/opt/openclaw-bootstrap/workspace/skills/crm/library/battlecards.json")
    rules     = load("/opt/openclaw-bootstrap/workspace/skills/crm/library/human_rules.json")
    return (
        f"{agents_md}\n\n---\nSOUL:\n{soul_md}\n\n"
        f"---\nBATTLECARDS:\n{cards}\n\n---\nHUMAN_RULES:\n{rules}\n\n"
        "Seu nome é RAFA. Voce representa EXCLUSIVAMENTE a Zind (zind.pro)."
    )


def call(system, user_msg):
    for model in MODELS:
        try:
            r = subprocess.run(
                ["curl", "-sf", "-X", "POST", PROXY,
                 "-H", "Content-Type: application/json",
                 "-H", f"Authorization: Bearer {TOKEN}",
                 "-d", json.dumps({
                     "model": model,
                     "messages": [
                         {"role": "system", "content": system},
                         {"role": "user",   "content": user_msg}
                     ],
                     "max_tokens": 200
                 })],
                capture_output=True, text=True, timeout=25
            )
            d = json.loads(r.stdout)
            if "choices" in d:
                return d["choices"][0]["message"]["content"].strip(), model
        except Exception:
            continue
    return "[FALHOU]", "?"


def show(label, text, model=""):
    short = model.split("/")[-1] if model else ""
    ok = "✅" if len(text) <= 300 and not text.startswith("[FALHOU]") else "⚠️"
    print(f"\n{label} {ok} [{short}] ({len(text)}ch)")
    print(f'  → "{text}"')


SYS_QUAL = build_system("qualifier")
SYS_COLD = build_system("cold-contact")

# ── Cenário 1: Gatekeeper passa contato ─────────────────────────────────────
print("=" * 60)
print("CENÁRIO 1 — Gatekeeper fornece contato do síndico (Etapa 1D)")
print("=" * 60)

show("[Agente já enviou]",
     "Sou o Rafa da Zind (zind.pro). Preciso falar com o síndico responsável sobre "
     "um sistema exclusivo pra síndicos profissionais. Me passa o contato direto dele? Obrigado!")

gk = "O síndico responsável é o João Silva, pode falar pelo WhatsApp: 11 99123-4567"
print(f'\n[Gatekeeper responde]\n  → "{gk}"')

resp1, m1 = call(SYS_QUAL, (
    f"LEAD_ID: sim-adm-central\nINTENT: bot_gatekeeper\nSTAGE: lead\n"
    f"MENSAGEM_DO_LEAD: {gk}\n\n"
    "CONTEXTO: gatekeeper da Administradora Central forneceu contato do síndico. "
    "Fonte: Administradora Central. Aplicar Etapa 1D do Protocolo 2.\n\n"
    "Retorne no formato:\n[OUTREACH_NOVO_CONTATO:{telefone}]\n{mensagem_de_abertura}"
))
show("[Qualifier Etapa 1D — dispatch]", resp1, m1)
has_tag = "[OUTREACH_NOVO_CONTATO:" in resp1
lines   = resp1.split("\n", 1)
has_msg = len(lines) > 1 and len(lines[1].strip()) > 0
print(f"  Tag dispatch: {'✅' if has_tag else '❌'}")
print(f"  Mensagem de abertura: {'✅' if has_msg else '❌'}")
if has_tag and has_msg:
    print(f"  Telefone: {lines[0]}")
    print(f"  Msg: \"{lines[1].strip()}\"")

# ── Cenário 2: Abertura com indicado ────────────────────────────────────────
print("\n" + "=" * 60)
print("CENÁRIO 2 — Protocolo Indicação (1ª mensagem ao João)")
print("=" * 60)

resp2, m2 = call(SYS_COLD, (
    "LEAD_ID: joao-silva-sp\nINTENT: greeting\nSTAGE: lead\n"
    "DOR: retrabalho em gestão condominial\n"
    "SINAL: indicado pela Administradora Central — atendente passou o contato\n"
    "FIT: alta\nTOM: direto e casual\nMENSAGEM_DO_LEAD: (inicio da conversa)\n\n"
    "CONTEXTO PRE-CARREGADO:\nnome: João Silva\ncidade: sao_paulo\n"
    "interaction_history: 0 eventos outbound\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp."
))
show("[Cold-contact Protocolo Indicação]", resp2, m2)
print(f"  Menciona fonte: {'✅' if 'administradora' in resp2.lower() or 'passou' in resp2.lower() else '❌'}")
print(f"  Sem pitch: {'✅' if len(resp2) < 160 else '⚠️'}")

# ── Cenário 3: João responde → Ação 2 ───────────────────────────────────────
print("\n" + "=" * 60)
print("CENÁRIO 3 — João responde positivo → Ação 2 (ferramenta)")
print("=" * 60)

resp3, m3 = call(SYS_COLD, (
    "LEAD_ID: joao-silva-sp\nINTENT: interest_uncertain\nSTAGE: lead\n"
    "SINAL: indicado pela Administradora Central\n"
    "MENSAGEM_DO_LEAD: Oi! Tudo bem, pode falar.\n\n"
    "CONTEXTO PRE-CARREGADO:\nnome: João Silva\ncidade: sao_paulo\n"
    "interaction_history: 1 evento outbound de cold-contact — executar Acao 2\n\n"
    "Retorne APENAS o texto da mensagem WhatsApp."
))
show("[Cold-contact Ação 2]", resp3, m3)
script_ok = "excel" in resp3.lower() or ("sistema" in resp3.lower() and "?" in resp3)
print(f"  Script de ferramenta: {'✅' if script_ok else '❌'}")

print("\n" + "=" * 60)
print("RESULTADO FINAL")
print(f"  Cenário 1 dispatch: {'✅' if has_tag and has_msg else '❌'}")
print(f"  Cenário 2 indicação: {'✅' if 'administradora' in resp2.lower() or 'passou' in resp2.lower() else '❌'}")
print(f"  Cenário 3 ferramenta: {'✅' if script_ok else '❌'}")
print("=" * 60)
