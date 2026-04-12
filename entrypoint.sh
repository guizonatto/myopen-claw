# Merge incremental das variáveis do .env local para ~/.openclaw/.env (sem sobrescrever ou duplicar)
if [ -f .env ]; then
    while IFS= read -r line; do
        # Ignora comentários e linhas em branco
        if [ -z "$line" ] || [[ "$line" =~ ^# ]]; then continue; fi
        key="$(echo "$line" | cut -d= -f1)"
        if ! grep -q "^$key=" ~/.openclaw/.env 2>/dev/null; then
            echo "$line" >> ~/.openclaw/.env
        fi
    done < .env
fi
#!/bin/sh
set -e

# Garante que está na raiz do projeto
cd /app 2>/dev/null || cd /workspace 2>/dev/null || cd "$(dirname "$0")"
APP_ROOT=$(pwd)
CONFIG_DIR="/root/.openclaw"

# --- BOOTSTRAP: Se o volume estiver vazio, copia arquivos default do build ---
if [ ! -f "$CONFIG_DIR/openclaw.json" ]; then
    echo "[BOOTSTRAP] Volume vazio, copiando arquivos default do build para o volume..."
    cp -r /app/configs "$CONFIG_DIR/workspace/" 2>/dev/null || true
    cp -r /app/skills "$CONFIG_DIR/workspace/" 2>/dev/null || true
    cp -r /app/crons "$CONFIG_DIR/workspace/" 2>/dev/null || true
    cp /app/openclaw.json "$CONFIG_DIR/openclaw.json" 2>/dev/null || true
fi

# Calcula hash SHA256 do conteúdo de configs/, skills/, mcps/*/schema, mcps/*/migrations
ONBOARD_HASH_FILE="$CONFIG_DIR/.onboard_version"
USER_VERSION_FILE="$CONFIG_DIR/.user_version"
CRON_HASH_FILE="$CONFIG_DIR/.cron_version"
CURRENT_HASH=$(find configs skills mcps/*/schema mcps/*/migrations -type f 2>/dev/null -exec cat {} + | sha256sum | awk '{print $1}')

# Checa versão do USER.md
USER_VERSION="$(grep '^versão:' configs/USER.md 2>/dev/null | awk -F: '{print $2}' | xargs)"
PREV_USER_VERSION=""
if [ -f "$USER_VERSION_FILE" ]; then
    PREV_USER_VERSION=$(cat "$USER_VERSION_FILE")
fi
PREV_HASH=""
if [ -f "$ONBOARD_HASH_FILE" ]; then
    PREV_HASH=$(cat "$ONBOARD_HASH_FILE")
fi

# Só executa onboarding se versão mudou OU hash mudou
NEEDS_ONBOARDING=0
if [ "$USER_VERSION" != "$PREV_USER_VERSION" ]; then
    echo "USER.md version changed. Forçando onboarding..."
    NEEDS_ONBOARDING=1
elif [ "$CURRENT_HASH" != "$PREV_HASH" ]; then
    echo "Onboarding changes detected. Rodando onboarding..."
    NEEDS_ONBOARDING=1
else
    echo "No onboarding changes detected. Skipping onboarding."
fi

# --- PLUGIN EVOLUTION: instala e habilita se não estiver presente ---
EVOLUTION_PLUGIN_DIR="/root/.openclaw/extensions/evolution"
EVOLUTION_PLUGIN_TGZ="/app/plugins/guizonatto-evolution-plugin-1.0.0.tgz"

if [ ! -d "$EVOLUTION_PLUGIN_DIR" ] && [ -f "$EVOLUTION_PLUGIN_TGZ" ]; then
    echo " >>> Instalando plugin Evolution..."
    node "$APP_ROOT/dist/index.js" plugins install "$EVOLUTION_PLUGIN_TGZ" --dangerously-force-unsafe-install
fi

if [ -f "$EVOLUTION_PLUGIN_TGZ" ]; then
    node "$APP_ROOT/dist/index.js" config set plugins.allow '["evolution"]' --strict-json 2>/dev/null || true
fi

echo " >>> [DEBUG] Checando Variáveis..."
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo " !!! ERRO: TELEGRAM_BOT_TOKEN VAZIO."
    exit 1
fi
echo " > Telegram Token OK."

if [ "$NEEDS_ONBOARDING" = "1" ]; then
    echo " >>> [ETAPA 1/5] Iniciando Onboarding..."
    # Lista de providers em ordem de preferência: z.ai, depois openai-codex
    PROVIDERS="zai-api-key openai-codex"
    API_KEY_VALUE=""
    for PROVIDER in $PROVIDERS; do
        VAR_NAME=$(echo "$PROVIDER" | tr '-' '_' | tr '[:lower:]' '[:upper:]')
        VAL=$(eval echo "\$$VAR_NAME")
        if [ -n "$VAL" ]; then
            AUTH_CHOICE="$PROVIDER"
            API_KEY_VAR_NAME="$VAR_NAME"
            API_KEY_VALUE="$VAL"
            echo "Usando provider: $PROVIDER"
            break
        fi
    done
    if [ -z "$API_KEY_VALUE" ]; then
        echo " !!! ERRO: Nenhuma chave de API encontrada para providers suportados (zai, openai-codex)."
        exit 1
    fi
    echo ">>> AI MODEL: $AUTH_CHOICE"

    node "$APP_ROOT/dist/index.js" onboard --non-interactive --accept-risk \
        --auth-choice "$AUTH_CHOICE" \
        --"$AUTH_CHOICE" "$API_KEY_VALUE" \
        --gateway-bind "$GATEWAY_BIND" \
        --gateway-auth password \
        --gateway-password "$ADMIN_PASSWORD" \
        --skip-channels --skip-health

    # Grava versão e hash após onboarding bem-sucedido
    echo "$USER_VERSION" > "$USER_VERSION_FILE"
    echo "$CURRENT_HASH" > "$ONBOARD_HASH_FILE"
    echo "Onboarding version/hash atualizados."

    echo " >>> [ETAPA 2/5] Ajustando Sandboxing e Browser..."
    [ "$ENABLE_SANDBOX" = "true" ] && node "$APP_ROOT/dist/index.js" config set agents.defaults.sandbox.mode "non-main"
    [ -n "$WEB_SEARCH_PROVIDER" ] && node "$APP_ROOT/dist/index.js" config set tools.web.search.provider "$WEB_SEARCH_PROVIDER"
    node "$APP_ROOT/dist/index.js" config set browser.enabled true --strict-json

    echo " >>> [ETAPA 3/5] Conectando Telegram..."
    node "$APP_ROOT/dist/index.js" channels add --channel telegram --token "$TELEGRAM_BOT_TOKEN"
    node "$APP_ROOT/dist/index.js" config set channels.telegram.allowFrom "[\"$TELEGRAM_USER_ID\"]" --strict-json
    node "$APP_ROOT/dist/index.js" config set channels.telegram.dmPolicy "allowlist"

    # Adiciona Discord se o token estiver configurado
    if [ -n "$DISCORD_BOT_TOKEN" ]; then
        echo " >>> [ETAPA 3.1/5] Conectando Discord..."
        node "$APP_ROOT/dist/index.js" config set channels.discord.token \
            --ref-provider default --ref-source env --ref-id DISCORD_BOT_TOKEN
        node "$APP_ROOT/dist/index.js" config set channels.discord.enabled true --strict-json
    fi

    # Adiciona WhatsApp se a variável de ambiente estiver habilitada
    if [ "$ENABLE_WHATSAPP" = "true" ]; then
        echo " >>> [ETAPA 3.5/5] Conectando WhatsApp (Baileys)..."
        # This command enables the Baileys plugin for WhatsApp.
        # On the first run, you will need to check the container logs for a QR code to scan with your phone.
        node "$APP_ROOT/dist/index.js" channels add --channel whatsapp --plugin paperclip-baileys --non-interactive
    fi

    echo " >>> [ETAPA 4/5] Registrando MCPs..."

    for mcp in crm memories shopping trends; do
        CONTAINER_NAME="mcp-$mcp"
        [ "$mcp" = "shopping" ] && CONTAINER_NAME="mcp-shopping-tracker"
        node "$APP_ROOT/dist/index.js" config set mcp.servers.$mcp.type "stdio"
        node "$APP_ROOT/dist/index.js" config set mcp.servers.$mcp.command "docker"
        node "$APP_ROOT/dist/index.js" config set mcp.servers.$mcp.args "[\"exec\",\"-i\",\"$CONTAINER_NAME\",\"python3\",\"/app/main.py\"]" --strict-json
    done

    echo " >>> [ETAPA 5/5] Instalando Skills..."
    if [ -n "$AUTO_INSTALL_SKILLS" ]; then
        for skill in $AUTO_INSTALL_SKILLS; do
            echo "  > Instalando: $skill"
            node "$APP_ROOT/dist/index.js" skills install "$skill" --force || echo "  ! Skill $skill pulada."
        done
    fi
    echo " >>> Setup concluído!"
fi

# --- SINCRONIZAÇÃO DE SKILLS ---
SKILLS_REPO_DIR="/root/.openclaw/workspace/skills_repo"
SKILLS_TARGET_DIR="/root/.openclaw/workspace/skills"

echo " >>> DEBUG: A URL recebida é: '$SKILLS_GIT_REPO'"
mkdir -p "$SKILLS_REPO_DIR"
mkdir -p "$SKILLS_TARGET_DIR"

if [ -d "$SKILLS_REPO_DIR/.git" ]; then
    echo "Atualizando repositório de skills..."
    cd "$SKILLS_REPO_DIR"
    git fetch origin main
    git reset --hard origin/main
else
    echo "Clonando repositório de skills..."
    rm -rf "$SKILLS_REPO_DIR"
    git clone "$SKILLS_GIT_REPO" "$SKILLS_REPO_DIR"
fi

cd "$APP_ROOT"

if [ -d "$SKILLS_REPO_DIR/skills" ]; then
    cp -r "$SKILLS_REPO_DIR/skills"/* "$SKILLS_TARGET_DIR/"
else
    cp -r "$SKILLS_REPO_DIR"/* "$SKILLS_TARGET_DIR/" 2>/dev/null || true
fi

wait_for_gateway() {
    attempt=1
    max_attempts="${1:-30}"

    while [ "$attempt" -le "$max_attempts" ]; do
        if openclaw cron list >/dev/null 2>&1; then
            return 0
        fi
        echo "  ... aguardando gateway ficar pronto ($attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    return 1
}

register_versioned_crons() {
    CRON_DIR="/root/.openclaw/workspace/crons"

    # Só registra se o hash dos .cron.md mudou desde o último registro
    CURRENT_CRON_HASH=$(find "$CRON_DIR" -name "*.cron.md" -type f 2>/dev/null -exec cat {} + | sha256sum | awk '{print $1}')
    PREV_CRON_HASH=""
    if [ -f "$CRON_HASH_FILE" ]; then
        PREV_CRON_HASH=$(cat "$CRON_HASH_FILE")
    fi

    if [ "$CURRENT_CRON_HASH" = "$PREV_CRON_HASH" ]; then
        echo " >>> Cronjobs sem alteração, pulando registro."
        return 0
    fi

    echo " >>> Registrando cronjobs versionados..."

    if ! ls "$CRON_DIR"/*.cron.md >/dev/null 2>&1; then
        echo "  ! Nenhum arquivo .cron.md encontrado em $CRON_DIR"
        return 0
    fi

    for cron_file in "$CRON_DIR"/*.cron.md; do
        cron_id=$(basename "$cron_file" .cron.md)
        # Extrai o --name do arquivo para checar se já existe
        cron_name=$(tr -d '\r' < "$cron_file" | grep -o -- '--name "[^"]*"' | head -1 | sed 's/--name "//;s/"$//')
        if [ -n "$cron_name" ] && openclaw cron list 2>/dev/null | grep -qF "\"$cron_name\""; then
            echo "  > Cronjob '$cron_name' já existe, pulando."
            continue
        fi
        echo "  > Registrando cronjob: $cron_id"
        if ! tr -d '\r' < "$cron_file" | sh; then
            echo "  ! Erro ao registrar cronjob $cron_id."
        fi
    done

    echo "$CURRENT_CRON_HASH" > "$CRON_HASH_FILE"
    echo " >>> Cronjobs registrados e hash atualizado."
}

echo " >>> Subindo Gateway OpenClaw..."
node "$APP_ROOT/dist/index.js" gateway run &
GATEWAY_PID=$!

if wait_for_gateway 45; then
    register_versioned_crons
else
    echo " !!! Gateway não ficou pronto a tempo; pulando registro de cronjobs."
fi

wait "$GATEWAY_PID"
