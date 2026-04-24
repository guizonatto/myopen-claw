#!/bin/sh
set -eu

REPO_ROOT="${1:-/repo}"
GATEWAY_CONTAINER="${OPENCLAW_GATEWAY_CONTAINER:-openclaw-gateway}"
OBSIDIAN_MCP_VERSION="${OBSIDIAN_MCP_VERSION:-1.0.6}"
OBSIDIAN_VAULT_PATH="${OBSIDIAN_VAULT_PATH:-/vault}"

ENTRYPOINT_FILE="$REPO_ROOT/entrypoint.sh"
OPENCLAW_JSON_FILE="$REPO_ROOT/openclaw.json"
VAULT_SKILL_FILE="$REPO_ROOT/skills/vault/SKILL.md"
TOOLS_DOC_FILE="$REPO_ROOT/configs/TOOLS.md"
MEMORY_DOC_FILE="$REPO_ROOT/configs/MEMORY.md"
AGENTS_DOC_FILE="$REPO_ROOT/configs/AGENTS.md"
INBOX_CRON_FILE="$REPO_ROOT/crons/vault_inbox_watcher.cron.md"
RAG_CRON_FILE="$REPO_ROOT/crons/vault_rag_indexer.cron.md"

LEGACY_USAGE_PATTERN='(list_notes|read_note|create_note|edit_note|move_note|search_notes|add_tag|remove_tag)[[:space:]]*["{]'
RUNTIME_LOG="$(mktemp)"
LEGACY_LOG="$(mktemp)"

cleanup() {
    rm -f "$RUNTIME_LOG" "$LEGACY_LOG"
}
trap cleanup EXIT

fail() {
    echo "[obsidian-contract] ERROR: $1" >&2
    exit 1
}

require_file() {
    if [ ! -f "$1" ]; then
        fail "Arquivo obrigatório ausente: $1"
    fi
}

for required_file in \
    "$ENTRYPOINT_FILE" \
    "$OPENCLAW_JSON_FILE" \
    "$VAULT_SKILL_FILE" \
    "$TOOLS_DOC_FILE" \
    "$MEMORY_DOC_FILE" \
    "$AGENTS_DOC_FILE" \
    "$INBOX_CRON_FILE" \
    "$RAG_CRON_FILE"
do
    require_file "$required_file"
done

echo "[obsidian-contract] Validando pin de versão no runtime..."
grep -q "obsidian-mcp@" "$ENTRYPOINT_FILE" || fail "entrypoint.sh não está pinando obsidian-mcp com versão."
grep -q "obsidian-mcp@" "$OPENCLAW_JSON_FILE" || fail "openclaw.json não está pinando obsidian-mcp com versão."

echo "[obsidian-contract] Validando contrato kebab-case em docs/skill/crons..."
for required_tool in \
    "list-available-vaults" \
    "search-vault" \
    "read-note" \
    "create-note" \
    "edit-note" \
    "move-note" \
    "add-tags" \
    "remove-tags"
do
    grep -q "$required_tool" "$VAULT_SKILL_FILE" || fail "Skill vault não referencia tool obrigatória: $required_tool"
    grep -q "$required_tool" "$TOOLS_DOC_FILE" || fail "TOOLS.md não referencia tool obrigatória: $required_tool"
done

if grep -E -n "$LEGACY_USAGE_PATTERN" \
    "$VAULT_SKILL_FILE" \
    "$TOOLS_DOC_FILE" \
    "$MEMORY_DOC_FILE" \
    "$AGENTS_DOC_FILE" \
    "$INBOX_CRON_FILE" \
    "$RAG_CRON_FILE" > "$LEGACY_LOG"
then
    cat "$LEGACY_LOG" >&2
    fail "Contrato legado snake_case ainda aparece em exemplos de uso."
fi

echo "[obsidian-contract] Validando tools reais registradas pelo obsidian-mcp no gateway..."
if ! docker ps --format '{{.Names}}' | grep -qx "$GATEWAY_CONTAINER"; then
    fail "Container do gateway não encontrado: $GATEWAY_CONTAINER"
fi

if ! docker exec "$GATEWAY_CONTAINER" sh -lc "set -eu
LOG_FILE=/tmp/obsidian-mcp-contract.log
rm -f \"\$LOG_FILE\"
rc=0
run_smoke() {
  rc=0
  rm -f \"\$LOG_FILE\"
  timeout 45s npx -y \"obsidian-mcp@${OBSIDIAN_MCP_VERSION}\" \"${OBSIDIAN_VAULT_PATH}\" > \"\$LOG_FILE\" 2>&1 || rc=\$?
}
run_smoke
if [ \"\$rc\" -ne 0 ] && [ \"\$rc\" -ne 124 ] && [ \"\$rc\" -ne 143 ] && grep -q 'Could not read package.json' \"\$LOG_FILE\"; then
  rm -rf /root/.npm/_npx >/dev/null 2>&1 || true
  run_smoke
fi
if [ \"\$rc\" -ne 0 ] && [ \"\$rc\" -ne 124 ] && [ \"\$rc\" -ne 143 ]; then
  cat \"\$LOG_FILE\"
  exit 11
fi
cat \"\$LOG_FILE\"
" > "$RUNTIME_LOG" 2>&1
then
    cat "$RUNTIME_LOG" >&2
    fail "Falha ao executar smoke test de obsidian-mcp no gateway."
fi

grep -q "Server initialized successfully" "$RUNTIME_LOG" || fail "Smoke test não confirmou inicialização do servidor."
for runtime_tool in \
    "create-note" \
    "read-note" \
    "edit-note" \
    "move-note" \
    "search-vault" \
    "add-tags" \
    "remove-tags" \
    "list-available-vaults"
do
    grep -q "Registering tool: $runtime_tool" "$RUNTIME_LOG" || fail "Tool não registrada no smoke test: $runtime_tool"
done

echo "[obsidian-contract] OK"
