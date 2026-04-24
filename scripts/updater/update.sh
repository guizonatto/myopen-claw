#!/bin/sh
# auto-updater — roda diariamente às 3h dentro do container openclaw-auto-updater
# Atualiza código e banco de dados de todos os MCPs sem perda de dados.
set -e

echo "[$(date)] === auto-update start ==="

# 1. Puxa código novo do git
cd /repo
git pull --ff-only origin main && echo "[$(date)] git pull OK" || echo "[$(date)] WARN: git pull falhou (pode ser branch local)"

# 2. Roda migrations de banco em cada MCP ativo (sem restart, sem perda de dados)
for container in mcp-crm mcp-trends mcp-shopping-tracker; do
    echo "[$(date)] alembic upgrade → $container"
    docker exec "$container" alembic upgrade head \
        && echo "[$(date)]   OK: $container" \
        || echo "[$(date)]   WARN: $container migration falhou"
done

# 3. Rebuild seletivo só se requirements.txt mudou (nova dependência Python)
CHANGED=$(git diff HEAD@{1} HEAD --name-only 2>/dev/null || true)

rebuild_if_needed() {
    mcp_dir="$1"
    service="$2"
    if echo "$CHANGED" | grep -q "mcps/$mcp_dir/requirements.txt"; then
        echo "[$(date)] requirements.txt mudou em $mcp_dir — rebuild $service"
        docker compose -f /repo/docker-compose.yml build "$service"
        docker compose -f /repo/docker-compose.yml up -d --no-deps "$service"
    fi
}

rebuild_if_needed "crm_mcp"             "mcp-crm"
rebuild_if_needed "trends_mcp"          "mcp-trends"
rebuild_if_needed "shopping_tracker_mcp" "mcp-shopping-tracker"
rebuild_if_needed "leads_mcp"           "mcp-leads"

# 4. Copia skills do repo principal direto para dentro do gateway
# (não depende de SKILLS_GIT_REPO — usa o repo que já foi clonado no servidor)
echo "[$(date)] copiando skills para o gateway..."
if [ -d "/repo/skills" ]; then
    docker cp /repo/skills/. openclaw-gateway:/root/.openclaw/workspace/skills/ \
        && echo "[$(date)] Skills copiadas OK" \
        || echo "[$(date)] WARN: copia de skills falhou"
else
    echo "[$(date)] WARN: /repo/skills nao encontrado"
fi

# 5. Sincroniza também via SKILLS_GIT_REPO se configurado (repo externo separado)
docker exec openclaw-gateway sh -c '
    REPO="/root/.openclaw/workspace/skills_repo"
    TARGET="/root/.openclaw/workspace/skills"
    if [ -d "$REPO/.git" ]; then
        cd "$REPO" && git pull --ff-only origin main 2>&1 || true
        if [ -d "$REPO/skills" ]; then
            cp -r "$REPO/skills"/* "$TARGET/" 2>/dev/null || true
        else
            cp -r "$REPO"/* "$TARGET/" 2>/dev/null || true
        fi
        echo "SKILLS_GIT_REPO sincronizado."
    fi
' 2>/dev/null || true

# 6. Valida contrato Obsidian (runtime + docs + skill + crons)
echo "[$(date)] validando contrato Obsidian..."
sh /repo/scripts/check_obsidian_contract.sh /repo \
    && echo "[$(date)] contrato Obsidian OK" \
    || { echo "[$(date)] ERRO: contrato Obsidian inválido"; exit 1; }

echo "[$(date)] === auto-update done ==="
