#!/bin/sh
set -e

# Caminho de configuração do Root
CONFIG_DIR="/root/.openclaw"

echo " >>> [DEBUG] Checando Variáveis..."
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo " !!! ERRO: TELEGRAM_BOT_TOKEN VAZIO."
    exit 1
else
    echo " > Telegram Token OK."
fi
echo ">>> AI MODEL: $AUTH_CHOICE"

# ETAPA 1: Setup Automatizado
if [ ! -f "$CONFIG_DIR/openclaw.json" ]; then
  echo " >>> [ETAPA 1/5] Iniciando Onboarding..."
  
  # Lógica para pegar a chave de API
  API_KEY_VAR_NAME=$(echo "$AUTH_CHOICE" | tr '-' '_' | tr '[a-z]' '[A-Z]')
  API_KEY_VALUE=$(eval echo \$$API_KEY_VAR_NAME)
  
  
  # Comando Onboard em linha única para evitar erro de '\'
  node dist/index.js onboard --non-interactive --accept-risk --auth-choice "$AUTH_CHOICE" --$AUTH_CHOICE "$API_KEY_VALUE" --gateway-bind "$GATEWAY_BIND" --gateway-auth password --gateway-password "$ADMIN_PASSWORD" --skip-channels --skip-health

  echo " >>> [ETAPA 2/5] Ajustando Sandboxing..."
  if [ "$ENABLE_SANDBOX" = "true" ]; then node dist/index.js config set agents.defaults.sandbox.mode "non-main"; fi
  if [ -n "$WEB_SEARCH_PROVIDER" ]; then node dist/index.js config set tools.web.search.provider "$WEB_SEARCH_PROVIDER"; fi

  echo " >>> [ETAPA 3/5] Conectando Telegram..."
  node dist/index.js channels add --channel telegram --token "$TELEGRAM_BOT_TOKEN"
  
  # ...e agora FORÇAMOS a lista de permissão com o seu ID do .env (Usando 'allowFrom')
  node dist/index.js config set channels.telegram.allowFrom "[\"$TELEGRAM_USER_ID\"]" --strict-json
  node dist/index.js config set channels.telegram.dmPolicy  "allowlist"
  
  
  echo " >>> [ETAPA 4/5] Registrando MCPs..."
  node dist/index.js config set mcp.servers.crm.type "stdio"
  node dist/index.js config set mcp.servers.crm.command "docker"
  node dist/index.js config set mcp.servers.crm.args '["exec","-i","mcp-crm","python3","/app/main.py"]' --strict-json

  node dist/index.js config set mcp.servers.memories.type "stdio"
  node dist/index.js config set mcp.servers.memories.command "docker"
  node dist/index.js config set mcp.servers.memories.args '["exec","-i","mcp-memories","python3","/app/main.py"]' --strict-json

  node dist/index.js config set mcp.servers.shopping.type "stdio"
  node dist/index.js config set mcp.servers.shopping.command "docker"
  node dist/index.js config set mcp.servers.shopping.args '["exec","-i","mcp-shopping-tracker","python3","/app/main.py"]' --strict-json

  node dist/index.js config set mcp.servers.trends.type "stdio"
  node dist/index.js config set mcp.servers.trends.command "docker"
  node dist/index.js config set mcp.servers.trends.args '["exec","-i","mcp-trends","python3","/app/main.py"]' --strict-json

  echo " >>> [ETAPA 5/5] Instalando Skills..."
  if [ -n "$AUTO_INSTALL_SKILLS" ]; then
    for skill in $AUTO_INSTALL_SKILLS; do
      echo "  > Instalando: $skill"
      node dist/index.js skills install "$skill" --force || echo "  ! Skill $skill pulada."
    done
  fi
  echo " >>> Setup concluído!"
  echo " >>> Reiniciando Server para aplicar configurações..."
  node dist/index.js gateway restart
fi

# Sincroniza/atualiza skills do GitHub (upsert robusto e seguro)
SKILLS_DIR="/root/.openclaw/workspace/skills"
if [ -d "$SKILLS_DIR/.git" ]; then
  cd "$SKILLS_DIR"
  if ! git remote get-url origin > /dev/null 2>&1; then
    git remote add origin "$SKILLS_GIT_REPO"
  fi
  echo "Atualizando skills do GitHub..."
  git pull origin main  # ou o branch correto
else
  echo "Inicializando repositório de skills do GitHub..."
  cd "$SKILLS_DIR"
  git init
  git remote add origin "$SKILLS_GIT_REPO"
  git pull origin main  # ou o branch correto
fi

# Upserta todas as skills da pasta sincronizada do GitHub
for skill_dir in /root/.openclaw/workspace/skills/*/; do
  if [ -f "$skill_dir/SKILL.md" ]; then
    skill_name=$(basename "$skill_dir")
    echo "Upsertando skill: $skill_name"
    node dist/index.js skills upsert "$skill_dir" || echo "  ! Falha ao upsertar $skill_name"
  fi
done

echo " >>> Subindo Gateway OpenClaw..."
exec node dist/index.js gateway run
