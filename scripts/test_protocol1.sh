#!/bin/bash
# Test Protocol 1 - all 4 actions via OpenClaw agent
set -e

AGENT="zind-crm-cold-contact"
MODEL="usage-router/google/gemini-2.5-flash"
SESSION="proto1-runtime-test-$$"

run_turn() {
    local acao=$1
    local history=$2
    local last_msg=$3
    local intent=$4

    local result
    result=$(OPENCLAW_ALLOW_INSECURE_PRIVATE_WS=1 openclaw agent \
        --agent "$AGENT" \
        --session-id "${SESSION}-a${acao}" \
        --model "$MODEL" \
        --message "LEAD_ID: sim-test
INTENT: ${intent}
STAGE: lead
DOR: retrabalho em follow-up e pagamento
SINAL: grupo de sindicos profissionais de SP
FIT: alta
TOM: direto e casual
MENSAGEM_DO_LEAD: ${last_msg}

CONTEXTO PRE-CARREGADO (nao chame search_contact):
nome: Joao
setor: gestao condominial
cidade: sao_paulo
interaction_history: ${history} eventos outbound de cold-contact - Acao ${acao}

Voce representa exclusivamente a Zind (zind.pro). Nunca cite outra empresa.
Retorne APENAS o texto da mensagem." \
        --json --timeout 60 2>/dev/null)

    echo "$result" | python3 -c "
import sys,json
d=json.load(sys.stdin)
r=d.get('result',d)
p=r.get('payloads',[])
m=r.get('meta',{}).get('agentMeta',{})
txt=p[0]['text'] if p else 'SEM RESPOSTA'
print(f'ACAO $acao: {txt}')
print(f'  modelo: {m.get(\"model\",\"?\")} | chars: {len(txt)}')
"
}

echo "=== TESTE PROTOCOLO 1 — $(date) ==="
echo ""

run_turn 1 0 "(inicio da conversa)" "greeting"
echo ""
run_turn 2 1 "Tudo bem sim!" "interest_uncertain"
echo ""
run_turn 3 2 "Uso o Excel pra tudo ainda." "interest_uncertain"
echo ""
run_turn 4 3 "Faz sentido, entendi como funciona." "interest_uncertain"

echo ""
echo "=== FIM ==="
