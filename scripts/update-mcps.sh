#!/bin/sh
# update-mcps.sh — Atualiza código e schema de todos os MCPs sem perda de dados.
# Rodar no servidor host: ./scripts/update-mcps.sh
# Cron sugerido: 0 3 * * * /path/to/repo/scripts/update-mcps.sh >> /var/log/update-mcps.log 2>&1

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "[$(date)] === update-mcps start ==="

# 1. Puxa código novo
git pull --ff-only origin main

# 2. Roda migrations em cada MCP (sem restart — volumes montados, uvicorn --reload cuida do código)
for container in mcp-crm mcp-memories mcp-trends mcp-shopping-tracker; do
    echo "[$(date)] alembic upgrade head → $container"
    docker exec "$container" alembic upgrade head || echo "WARN: $container migration failed"
done

# 3. Se requirements.txt mudou no último pull, rebuild do MCP afetado
CHANGED=$(git diff HEAD@{1} HEAD --name-only 2>/dev/null || true)

for mcp in crm_mcp memories_mcp trends_mcp shopping_tracker_mcp; do
    if echo "$CHANGED" | grep -q "mcps/$mcp/requirements.txt"; then
        service=$(echo "$mcp" | sed 's/_mcp//' | sed 's/_/-/g')
        [ "$mcp" = "shopping_tracker_mcp" ] && service="shopping-tracker"
        echo "[$(date)] requirements.txt mudou em $mcp — rebuild mcp-$service"
        docker compose build "mcp-$service"
        docker compose up -d --no-deps "mcp-$service"
    fi
done

# 4. Sincroniza skills no workspace do gateway (sem restart)
echo "[$(date)] sincronizando skills no gateway..."
docker exec openclaw-gateway sh -c '
    SKILLS_REPO="/root/.openclaw/workspace/skills_repo"
    SKILLS_TARGET="/root/.openclaw/workspace/skills"
    if [ -d "$SKILLS_REPO/.git" ]; then
        cd "$SKILLS_REPO" && git pull --ff-only origin main
        cp -r "$SKILLS_REPO/skills"/* "$SKILLS_TARGET/" 2>/dev/null || \
        cp -r "$SKILLS_REPO"/* "$SKILLS_TARGET/" 2>/dev/null || true
        echo "Skills atualizadas."
    else
        echo "WARN: skills_repo não encontrado no gateway."
    fi
' || echo "WARN: sync de skills falhou"

echo "[$(date)] === update-mcps done ==="
