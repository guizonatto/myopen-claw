"""Runtime test for Protocol 1 — invokes zind-crm-cold-contact via gateway."""
import json
import os
import subprocess
import sys

AGENT = "zind-crm-cold-contact"

TURNS = [
    {"acao": 1, "intent": "greeting",          "history": 0, "last_msg": "(inicio da conversa)"},
    {"acao": 2, "intent": "interest_uncertain", "history": 1, "last_msg": "Tudo bem sim, pode falar!"},
    {"acao": 3, "intent": "interest_uncertain", "history": 2, "last_msg": "Uso o Excel pra tudo ainda."},
    {"acao": 4, "intent": "interest_uncertain", "history": 3, "last_msg": "Interessante, como funciona?"},
]


def run_action(acao: int, intent: str, history: int, last_msg: str) -> dict:
    msg = (
        f"LEAD_ID: sim-test\n"
        f"INTENT: {intent}\n"
        f"STAGE: lead\n"
        f"DOR: retrabalho em follow-up e pagamento\n"
        f"SINAL: grupo de sindicos profissionais de SP\n"
        f"FIT: alta\n"
        f"TOM: direto e casual\n"
        f"MENSAGEM_DO_LEAD: {last_msg}\n\n"
        f"CONTEXTO PRE-CARREGADO (nao chame search_contact):\n"
        f"nome: Joao\nsetor: gestao condominial\ncidade: sao_paulo\n"
        f"interaction_history: {history} eventos outbound de cold-contact - Acao {acao}\n\n"
        f"Voce representa exclusivamente a Zind (zind.pro). Nunca cite outra empresa.\n"
        f"Retorne APENAS o texto da mensagem."
    )

    env = {**os.environ, "OPENCLAW_ALLOW_INSECURE_PRIVATE_WS": "1"}
    proc = subprocess.run(
        ["openclaw", "agent", "--agent", AGENT,
         "--session-id", f"proto1-t{acao}-{os.getpid()}",
         "--message", msg, "--json", "--timeout", "90"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, timeout=120,
    )

    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace")

    # Extract JSON from stdout (there may be log lines before it)
    start = out.find("{")
    end = out.rfind("}") + 1
    text, model = "?", "?"
    if start >= 0 and end > start:
        try:
            data = json.loads(out[start:end])
            r = data.get("result", data)
            payloads = r.get("payloads", [])
            text = payloads[0]["text"] if payloads else "SEM PAYLOAD"
            model = r.get("meta", {}).get("agentMeta", {}).get("model", "?")
        except Exception as e:
            text = f"[JSON ERR] {e} | out={out[:200]}"
    else:
        text = f"[EMPTY] err={err[:300]}"

    return {"text": text, "model": model, "chars": len(text)}


print("=" * 60)
print("TESTE PROTOCOLO 1 — zind-crm-cold-contact (via gateway)")
print("=" * 60)

for t in TURNS:
    print(f"\n--- Ação {t['acao']} ---")
    print(f"Lead: \"{t['last_msg']}\"")
    r = run_action(t["acao"], t["intent"], t["history"], t["last_msg"])
    print(f"Agente: \"{r['text']}\"")
    print(f"chars={r['chars']} | modelo={r['model']}")

    issues = []
    if r["chars"] > 220:      issues.append(f"LONGO {r['chars']}ch")
    if "condoseg" in r["text"].lower():  issues.append("CITA CONDOSEG")
    if r["text"].startswith("["):        issues.append("ERRO/VAZIO")
    print("STATUS:", "[FAIL] " + " | ".join(issues) if issues else "[OK]")

print("\n" + "=" * 60)
