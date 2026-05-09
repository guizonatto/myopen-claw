#!/usr/bin/env bash
# test_agents_gateway.sh
# Smoke test of each zind-crm-* agent via OpenClaw CLI inside the gateway container.
# Requires: gateway running (docker compose ps openclaw-gateway)
# Usage: bash scripts/test_agents_gateway.sh [LEAD_UUID]
#
# What this tests:
#   - Each agent is reachable and responds without crashing
#   - Responses are non-empty
#   - No "Draft failed" or error payloads
#   - Basic response quality: non-empty, within char limits

set -euo pipefail

LEAD_ID="${1:-75a600f0-14c5-472b-8bf5-e4a7fd783f83}"
GATEWAY_URL="http://127.0.0.1:18789"
TIMEOUT=120
PASS=0
FAIL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}PASS${NC} $1"; ((PASS++)); }
log_fail() { echo -e "${RED}FAIL${NC} $1"; ((FAIL++)); }
log_info() { echo -e "${YELLOW}INFO${NC} $1"; }

run_agent() {
    local agent="$1"
    local message="$2"
    docker exec openclaw-gateway sh -c \
        "OPENCLAW_GATEWAY_URL=${GATEWAY_URL} openclaw agent --agent ${agent} --json --timeout ${TIMEOUT} --message '${message}' 2>/dev/null" \
        2>&1
}

check_response() {
    local agent="$1"
    local output="$2"
    local scenario="$3"

    if echo "$output" | grep -q '"payloads"'; then
        local text
        text=$(echo "$output" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    payloads = d.get('payloads', [])
    texts = [p.get('text','') for p in payloads if p.get('text')]
    print('\n'.join(texts))
except:
    print('')
" 2>/dev/null)

        if [ -z "$text" ] || echo "$text" | grep -qi "draft failed"; then
            log_fail "[$agent] $scenario — empty or draft failed"
            log_info "output: $(echo "$output" | head -3)"
            return 1
        fi

        local char_count
        char_count=$(echo "$text" | awk '{ total += length($0) } END { print total }')
        if [ "$char_count" -gt 360 ]; then
            log_fail "[$agent] $scenario — response too long ($char_count chars, max ~360 for 2 chunks)"
            log_info "text: $text"
            return 1
        fi

        log_pass "[$agent] $scenario ($char_count chars)"
        log_info "  → $text" | head -c 200
        echo
        return 0
    else
        log_fail "[$agent] $scenario — no payloads in response"
        log_info "raw: $(echo "$output" | head -5)"
        return 1
    fi
}

echo "======================================================"
echo "  Zind CRM Agent Gateway Smoke Tests"
echo "  Lead: $LEAD_ID"
echo "  Gateway: $GATEWAY_URL"
echo "======================================================"
echo

# ── Build context template ────────────────────────────────────────────────────

COLD_CTX="LEAD_ID: ${LEAD_ID}
INTENT: greeting
STAGE: lead
DOR: retrabalho em follow-up e cobranca
SINAL: visitou o site da Zind
FIT: alto
TOM: direto
MENSAGEM_DO_LEAD: Oi tudo bem?"

QUAL_PRICE_CTX="LEAD_ID: ${LEAD_ID}
INTENT: objection_price
STAGE: qualificado
DOR: retrabalho em follow-up
SINAL: visitou site
FIT: medio
TOM: direto
MENSAGEM_DO_LEAD: Acho muito caro para o que oferece"

QUAL_PROOF_CTX="LEAD_ID: ${LEAD_ID}
INTENT: request_proof
STAGE: qualificado
DOR: retrabalho em cobranca
SINAL: (none)
FIT: alto
TOM: formal
MENSAGEM_DO_LEAD: Pode me mostrar algum exemplo de uso?"

CLOSER_CTX="LEAD_ID: ${LEAD_ID}
INTENT: interest_positive
STAGE: qualificado
DOR: retrabalho em follow-up
SINAL: clicou no link do video
FIT: alto
TOM: direto
MENSAGEM_DO_LEAD: Gostei, faz sentido para nos"

HANDOVER_HUMAN_CTX="LEAD_ID: ${LEAD_ID}
INTENT: request_human
STAGE: qualificado
DOR: (none)
SINAL: (none)
FIT: (none)
TOM: formal
MENSAGEM_DO_LEAD: Quero falar com uma pessoa real"

HANDOVER_NO_INT_CTX="LEAD_ID: ${LEAD_ID}
INTENT: no_interest
STAGE: lead
DOR: (none)
SINAL: (none)
FIT: (none)
TOM: neutro
MENSAGEM_DO_LEAD: Nao tenho interesse, podem me remover"

HANDOVER_ESCAL_CTX="LEAD_ID: ${LEAD_ID}
INTENT: escalate_frustration
STAGE: lead
DOR: (none)
SINAL: (none)
FIT: (none)
TOM: neutro
MENSAGEM_DO_LEAD: Isso e ridiculo, que absurdo de atendimento"

# ── Run tests ─────────────────────────────────────────────────────────────────

log_info "Testing zind-crm-cold-contact..."
OUT=$(run_agent "zind-crm-cold-contact" "$COLD_CTX")
check_response "zind-crm-cold-contact" "$OUT" "greeting → first contact"

echo

log_info "Testing zind-crm-qualifier (price objection)..."
OUT=$(run_agent "zind-crm-qualifier" "$QUAL_PRICE_CTX")
check_response "zind-crm-qualifier" "$OUT" "objection_price → battlecard reframe"

log_info "Testing zind-crm-qualifier (request proof)..."
OUT=$(run_agent "zind-crm-qualifier" "$QUAL_PROOF_CTX")
check_response "zind-crm-qualifier" "$OUT" "request_proof → material offer"

echo

log_info "Testing zind-crm-closer (interest positive)..."
OUT=$(run_agent "zind-crm-closer" "$CLOSER_CTX")
check_response "zind-crm-closer" "$OUT" "interest_positive → next step CTA"

echo

log_info "Testing zind-crm-handover (request human)..."
OUT=$(run_agent "zind-crm-handover" "$HANDOVER_HUMAN_CTX")
check_response "zind-crm-handover" "$OUT" "request_human → transition message"

log_info "Testing zind-crm-handover (no interest)..."
OUT=$(run_agent "zind-crm-handover" "$HANDOVER_NO_INT_CTX")
check_response "zind-crm-handover" "$OUT" "no_interest → respectful exit"

log_info "Testing zind-crm-handover (escalation)..."
OUT=$(run_agent "zind-crm-handover" "$HANDOVER_ESCAL_CTX")
check_response "zind-crm-handover" "$OUT" "escalate_frustration → de-escalation"

echo
echo "======================================================"
echo -e "  Results: ${GREEN}${PASS} passed${NC} / ${RED}${FAIL} failed${NC}"
echo "======================================================"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
