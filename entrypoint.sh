#!/bin/bash
set -euo pipefail

# ── Bootstrap de sistema (installs em runtime; sem RUN no Dockerfile) ─────────
chown -R root:root /app/extensions 2>/dev/null || true

if ! command -v docker >/dev/null 2>&1; then
    echo "[SYS] Instalando Docker CLI..."
    apt-get update -qq && apt-get install -y --no-install-recommends docker.io \
        && rm -rf /var/lib/apt/lists/* || echo "[SYS] docker.io indisponivel, continuando."
fi

if [ ! -d "/opt/openclaw-bootstrap/extensions/memclaw" ] && \
   [ -f "/opt/openclaw-bootstrap/memclaw.tgz" ]; then
    echo "[SYS] Instalando MemClaw..."
    mkdir -p /opt/openclaw-bootstrap/extensions/memclaw
    tar -xzf /opt/openclaw-bootstrap/memclaw.tgz \
        -C /opt/openclaw-bootstrap/extensions/memclaw --strip-components=1
    cd /opt/openclaw-bootstrap/extensions/memclaw && npm install --omit=dev
fi
# ─────────────────────────────────────────────────────────────────────────────

cd /app 2>/dev/null || cd /workspace 2>/dev/null || cd "$(dirname "$0")"
APP_ROOT=$(pwd)
CONFIG_DIR="/root/.openclaw"
WORKSPACE_DIR="$CONFIG_DIR/workspace"
BOOTSTRAP_DIR="/opt/openclaw-bootstrap"
SOURCE_WORKSPACE="$BOOTSTRAP_DIR/workspace"
GIT_STAGING_DIR="$CONFIG_DIR/git-staging"

ONBOARD_HASH_FILE="$CONFIG_DIR/.onboard_version"
USER_VERSION_FILE="$CONFIG_DIR/.user_version"
CRON_HASH_FILE="$CONFIG_DIR/.cron_version"

mkdir -p "$CONFIG_DIR" "$WORKSPACE_DIR" "$CONFIG_DIR/hooks"
mkdir -p "$CONFIG_DIR/extensions"

init_git_staging() {
    if [ -z "${GITHUB_TOKEN:-}" ] || [ -z "${GITHUB_ORG:-}" ] || [ -z "${GITHUB_REPO:-}" ]; then
        echo " >>> [GIT] GITHUB_TOKEN/ORG/REPO não definidos — auto-push desabilitado."
        return 0
    fi

    local remote_url="https://${GITHUB_TOKEN}@github.com/${GITHUB_ORG}/${GITHUB_REPO}.git"

    if [ ! -d "$GIT_STAGING_DIR/.git" ]; then
        echo " >>> [GIT] Clonando repositório para auto-push staging..."
        if ! git clone "$remote_url" "$GIT_STAGING_DIR" --depth=1 2>&1 | tail -3; then
            echo " !!! [GIT] Falha ao clonar — verifique GITHUB_TOKEN/ORG/REPO no .env. Auto-push desabilitado."
            return 0
        fi
        git -C "$GIT_STAGING_DIR" config user.email "openclaw-bot@noreply"
        git -C "$GIT_STAGING_DIR" config user.name "OpenClaw Bot"
    else
        echo " >>> [GIT] Atualizando clone staging..."
        git -C "$GIT_STAGING_DIR" remote set-url origin "$remote_url" 2>/dev/null || true
        git -C "$GIT_STAGING_DIR" pull origin main --ff-only 2>&1 | tail -3 || true
    fi
}

seed_bootstrap() {
    if [ ! -f "$CONFIG_DIR/openclaw.json" ]; then
        echo "[BOOTSTRAP] Volume vazio, copiando arquivos default do build para o volume..."
        mkdir -p \
            "$WORKSPACE_DIR/configs" \
            "$WORKSPACE_DIR/skills" \
            "$WORKSPACE_DIR/crons" \
            "$WORKSPACE_DIR/scripts"

        cp -r "$SOURCE_WORKSPACE/configs/." "$WORKSPACE_DIR/configs/" 2>/dev/null || true
        cp -r "$SOURCE_WORKSPACE/skills/." "$WORKSPACE_DIR/skills/" 2>/dev/null || true
        cp -r "$SOURCE_WORKSPACE/crons/." "$WORKSPACE_DIR/crons/" 2>/dev/null || true
        cp -r "$SOURCE_WORKSPACE/scripts/." "$WORKSPACE_DIR/scripts/" 2>/dev/null || true
        cp -r "$BOOTSTRAP_DIR/hooks/." "$CONFIG_DIR/hooks/" 2>/dev/null || true
        cp "$BOOTSTRAP_DIR/openclaw.json" "$CONFIG_DIR/openclaw.json" 2>/dev/null || true
    fi

    if [ -d "$BOOTSTRAP_DIR/extensions/memclaw" ] && [ ! -d "$CONFIG_DIR/extensions/memclaw" ]; then
        mkdir -p "$CONFIG_DIR/extensions"
        cp -r "$BOOTSTRAP_DIR/extensions/memclaw" "$CONFIG_DIR/extensions/memclaw"
    fi
}

seed_bootstrap

reconcile_openclaw_config() {
    local config_path="$CONFIG_DIR/openclaw.json"

    if [ ! -f "$config_path" ]; then
        echo " >>> Nenhum openclaw.json encontrado para reconciliar."
        return 0
    fi

    echo " >>> Reconciliando configuracao persistida do OpenClaw..."
    CONFIG_PATH="$config_path" \
    CORTEX_MEM_URL_VALUE="${CORTEX_MEM_URL:-http://cortex-mem:8085}" \
    ZAI_API_BASE_URL_VALUE="${ZAI_API_BASE_URL:-https://api.z.ai/api/paas/v4}" \
    ZAI_API_KEY_VALUE="${ZAI_API_KEY:-}" \
    ZAI_MODEL_VALUE="${ZAI_MODEL:-GLM-4.7}" \
    EMBEDDING_MODEL_VALUE="${EMBEDDING_MODEL:-qwen3-embedding:0.6b}" \
    OLLAMA_MODEL_VALUE="${OLLAMA_MODEL:-gemma4}" \
    NVIDIA_API_KEY_VALUE="${NVIDIA_API_KEY:-}" \
    NVIDIA_MODEL_VALUE="${NVIDIA_MODEL:-google/gemma-4-31b-it:latest}" \
    OPENROUTER_MODEL_VALUE="${OPENROUTER_MODEL:-google/gemma-4-31b-it:free}" \
    node <<'EOF'
const fs = require("fs");

const configPath = process.env.CONFIG_PATH;
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const rawModel = process.env.ZAI_MODEL_VALUE || "GLM-4.7";
let llmModel = rawModel;

if (llmModel.startsWith("zai/")) {
  llmModel = llmModel.slice(4);
}
if (/^glm-/i.test(llmModel)) {
  llmModel = llmModel.toUpperCase();
}

// Reparar providers que faltam o campo 'models' (array obrigatorio no schema)
if (config.models?.providers) {
  for (const key of Object.keys(config.models.providers)) {
    if (!Array.isArray(config.models.providers[key].models)) {
      config.models.providers[key].models = [];
    }
  }
}

config.mcp ??= {};
config.mcp.servers ??= {};
delete config.mcp.servers["mcp-memories"];
delete config.mcp.servers["memories"];

config.plugins ??= {};
config.plugins.slots ??= {};
config.plugins.entries ??= {};
config.plugins.slots.memory = "memclaw";
config.plugins.entries.memclaw = {
  enabled: true,
  config: {
    serviceUrl: process.env.CORTEX_MEM_URL_VALUE,
    tenantId: "tenant_claw",
    autoStartServices: false,
    llmApiBaseUrl: process.env.ZAI_API_BASE_URL_VALUE,
    llmApiKey: process.env.ZAI_API_KEY_VALUE,
    llmModel,
    embeddingApiBaseUrl: "http://host.docker.internal:11434/v1",
    embeddingApiKey: "ollama",
    embeddingModel: process.env.EMBEDDING_MODEL_VALUE,
  },
};

config.plugins.allow = Array.from(
  new Set([...(config.plugins.allow ?? []), "memclaw", "evolution"])
);

const ollamaModel = process.env.OLLAMA_MODEL_VALUE || "gemma4";
// Garantir que o provider ollama usa host.docker.internal, nunca o hostname 'ollama'
config.models ??= {};
config.models.providers ??= {};
config.models.providers.ollama ??= {};
config.models.providers.ollama.baseUrl = "http://host.docker.internal:11434";
config.models.providers.ollama.apiKey ??= "ollama-local";
config.models.providers.ollama.api ??= "ollama";
const nvidiaKey = process.env.NVIDIA_API_KEY_VALUE || "";
const nvidiaModel = process.env.NVIDIA_MODEL_VALUE || "google/gemma-4-31b-it:latest";
const openrouterModel = process.env.OPENROUTER_MODEL_VALUE || "google/gemma-4-31b-it:free";
config.agents ??= {};
config.agents.defaults ??= {};
config.agents.defaults.memorySearch = { enabled: false };
if (nvidiaKey) {
  config.agents.defaults.model = {
    primary: `nvidia/${nvidiaModel}`,
    fallbacks: [`openrouter/${openrouterModel}`, `ollama/${ollamaModel}`],
  };
  config.models ??= {};
  config.models.providers ??= {};
  config.models.providers.nvidia = {
    apiKey: nvidiaKey,
    baseUrl: "https://integrate.api.nvidia.com/v1",
    api: "openai-completions",
    models: [],
  };
} else {
  config.agents.defaults.model = { primary: `ollama/${ollamaModel}`, fallbacks: [] };
}

config.gateway ??= {};
config.gateway.controlUi ??= {};
const origins = new Set(config.gateway.controlUi.allowedOrigins ?? []);
["http://localhost:8090"].forEach(o => origins.add(o));
config.gateway.controlUi.allowedOrigins = Array.from(origins);

fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`);
EOF
}

reconcile_openclaw_config
init_git_staging

echo " >>> Reparando configuracao (doctor --fix)..."
node "$APP_ROOT/dist/index.js" doctor --fix 2>/dev/null || true

if [ -n "${NVIDIA_API_KEY:-}" ]; then
    echo " >>> Configurando NVIDIA NIM como provider primario..."
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.apiKey "${NVIDIA_API_KEY:-}" 2>/dev/null || true
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.baseUrl "https://integrate.api.nvidia.com/v1" 2>/dev/null || true
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.api "openai-completions" 2>/dev/null || true
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.models "[]" --strict-json 2>/dev/null || true
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.primary "nvidia/${NVIDIA_MODEL:-google/gemma-4-31b-it:latest}" 2>/dev/null || true
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.fallbacks "[\"openrouter/${OPENROUTER_MODEL:-google/gemma-4-31b-it:free}\",\"ollama/${OLLAMA_MODEL:-gemma4}\"]" --strict-json 2>/dev/null || true
else
    echo " >>> Configurando modelo Ollama..."
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.primary "ollama/${OLLAMA_MODEL:-gemma4}" 2>/dev/null || true
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.fallbacks "[]" --strict-json 2>/dev/null || true
fi

CURRENT_HASH="$(
    find \
        "$SOURCE_WORKSPACE/configs" \
        "$SOURCE_WORKSPACE/skills" \
        mcps/*/schema \
        mcps/*/migrations \
        -type f 2>/dev/null -exec cat {} + | sha256sum | awk '{print $1}'
)"

USER_VERSION="$(
    grep '^versão:' "$SOURCE_WORKSPACE/configs/USER.md" 2>/dev/null | awk -F: '{print $2}' | xargs
)"
PREV_USER_VERSION=""
if [ -f "$USER_VERSION_FILE" ]; then
    PREV_USER_VERSION=$(cat "$USER_VERSION_FILE")
fi

PREV_HASH=""
if [ -f "$ONBOARD_HASH_FILE" ]; then
    PREV_HASH=$(cat "$ONBOARD_HASH_FILE")
fi

NEEDS_ONBOARDING=0
if [ "$USER_VERSION" != "$PREV_USER_VERSION" ]; then
    echo "USER.md version changed. Forcando onboarding..."
    NEEDS_ONBOARDING=1
elif [ "$CURRENT_HASH" != "$PREV_HASH" ]; then
    echo "Onboarding changes detected. Rodando onboarding..."
    NEEDS_ONBOARDING=1
else
    echo "No onboarding changes detected. Skipping onboarding."
fi

EVOLUTION_PLUGIN_DIR="/root/.openclaw/extensions/evolution"
EVOLUTION_PLUGIN_TGZ="/app/plugins/guizonatto-evolution-plugin-1.0.0.tgz"

if [ ! -d "$EVOLUTION_PLUGIN_DIR" ] && [ -f "$EVOLUTION_PLUGIN_TGZ" ]; then
    echo " >>> Instalando plugin Evolution..."
    node "$APP_ROOT/dist/index.js" plugins install "$EVOLUTION_PLUGIN_TGZ" --dangerously-force-unsafe-install
fi

if [ -f "$EVOLUTION_PLUGIN_TGZ" ]; then
    node "$APP_ROOT/dist/index.js" config set plugins.allow '["evolution","memclaw"]' --strict-json 2>/dev/null || true
fi

echo " >>> [DEBUG] Checando Variaveis..."
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo " !!! ERRO: TELEGRAM_BOT_TOKEN VAZIO."
    exit 1
fi
echo " > Telegram Token OK."

if [ "$NEEDS_ONBOARDING" = "1" ]; then
    echo " >>> [ETAPA 1/5] Iniciando Onboarding..."
    API_KEY_VALUE=""
    if [ -n "${NVIDIA_API_KEY:-}" ]; then
        AUTH_CHOICE="skip"
        API_KEY_VALUE="${NVIDIA_API_KEY}"
        echo "Usando provider: nvidia (auth-choice skip)"
    fi
    PROVIDERS="openrouter-api-key zai-api-key openai-codex"
    for PROVIDER in $PROVIDERS; do
        VAR_NAME=$(echo "$PROVIDER" | tr '-' '_' | tr '[:lower:]' '[:upper:]')
        VAL=$(eval echo "\$$VAR_NAME")
        if [ -n "$VAL" ]; then
            AUTH_CHOICE="$PROVIDER"
            API_KEY_VALUE="$VAL"
            echo "Usando provider: $PROVIDER"
            break
        fi
    done

    if [ -z "$API_KEY_VALUE" ]; then
        echo " !!! ERRO: Nenhuma chave de API encontrada para providers suportados (openrouter, zai, openai-codex)."
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

    echo "$USER_VERSION" > "$USER_VERSION_FILE"
    echo "$CURRENT_HASH" > "$ONBOARD_HASH_FILE"
    echo "Onboarding version/hash atualizados."

    echo " >>> [ETAPA 2/5] Ajustando Sandboxing, Browser e Ollama..."
    [ "${ENABLE_SANDBOX:-}" = "true" ] && node "$APP_ROOT/dist/index.js" config set agents.defaults.sandbox.mode "non-main"
    [ -n "${WEB_SEARCH_PROVIDER:-}" ] && node "$APP_ROOT/dist/index.js" config set tools.web.search.provider "$WEB_SEARCH_PROVIDER"
    node "$APP_ROOT/dist/index.js" config set browser.enabled true --strict-json

    echo "  > Configurando OpenRouter como provider principal..."
    node "$APP_ROOT/dist/index.js" config set models.providers.openrouter.apiKey "${OPENROUTER_API_KEY:-}"
    node "$APP_ROOT/dist/index.js" config set models.providers.openrouter.baseUrl "${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
    node "$APP_ROOT/dist/index.js" config set models.providers.openrouter.api "openai-completions"
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.primary "openrouter/${OPENROUTER_MODEL:-google/gemma-4-31b-it:free}"
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.fallbacks "[\"ollama/${OLLAMA_MODEL:-gemma4}\"]" --strict-json

    echo "  > Mantendo Ollama configurado como fallback local..."
    node "$APP_ROOT/dist/index.js" config set models.providers.ollama.apiKey "${OLLAMA_API_KEY:-ollama-local}"
    node "$APP_ROOT/dist/index.js" config set models.providers.ollama.baseUrl "http://host.docker.internal:11434"
    node "$APP_ROOT/dist/index.js" config set models.providers.ollama.api "ollama"

    echo "  > Configurando NVIDIA NIM como provider primário..."
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.apiKey "${NVIDIA_API_KEY:-}"
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.baseUrl "https://integrate.api.nvidia.com/v1"
    node "$APP_ROOT/dist/index.js" config set models.providers.nvidia.api "openai-completions"
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.primary "nvidia/${NVIDIA_MODEL:-google/gemma-4-31b-it:latest}"
    node "$APP_ROOT/dist/index.js" config set agents.defaults.model.fallbacks "[\"openrouter/${OPENROUTER_MODEL:-google/gemma-4-31b-it:free}\",\"ollama/${OLLAMA_MODEL:-gemma4}\"]" --strict-json

    echo " >>> [ETAPA 3/5] Conectando Telegram..."
    node "$APP_ROOT/dist/index.js" channels add --channel telegram --token "$TELEGRAM_BOT_TOKEN"
    node "$APP_ROOT/dist/index.js" config set channels.telegram.allowFrom "[\"$TELEGRAM_USER_ID\"]" --strict-json
    node "$APP_ROOT/dist/index.js" config set channels.telegram.dmPolicy "allowlist"

    if [ -n "${DISCORD_BOT_TOKEN:-}" ]; then
        echo " >>> [ETAPA 3.1/5] Conectando Discord..."
        node "$APP_ROOT/dist/index.js" config set channels.discord.token \
            --ref-provider default --ref-source env --ref-id DISCORD_BOT_TOKEN
        node "$APP_ROOT/dist/index.js" config set channels.discord.enabled true --strict-json
    fi

    if [ "${ENABLE_WHATSAPP:-}" = "true" ]; then
        echo " >>> [ETAPA 3.5/5] Conectando WhatsApp (Baileys)..."
        node "$APP_ROOT/dist/index.js" channels add --channel whatsapp --plugin paperclip-baileys --non-interactive
    fi

    echo " >>> [ETAPA 4/5] Registrando MCPs..."
    for mcp in crm shopping trends; do
        CONTAINER_NAME="mcp-$mcp"
        [ "$mcp" = "shopping" ] && CONTAINER_NAME="mcp-shopping-tracker"
        node "$APP_ROOT/dist/index.js" config set mcp.servers.$mcp.type "stdio"
        node "$APP_ROOT/dist/index.js" config set mcp.servers.$mcp.command "docker"
        node "$APP_ROOT/dist/index.js" config set mcp.servers.$mcp.args "[\"exec\",\"-i\",\"$CONTAINER_NAME\",\"python3\",\"/app/main.py\"]" --strict-json
    done

    echo "  > Registrando MCP: obsidian"
    node "$APP_ROOT/dist/index.js" config set mcp.servers.obsidian.type "stdio"
    node "$APP_ROOT/dist/index.js" config set mcp.servers.obsidian.command "npx"
    node "$APP_ROOT/dist/index.js" config set mcp.servers.obsidian.args '["-y","obsidian-mcp","/vault"]' --strict-json

    echo " >>> [ETAPA 5/5] Instalando Skills..."
    if [ -n "${AUTO_INSTALL_SKILLS:-}" ]; then
        for skill in $AUTO_INSTALL_SKILLS; do
            echo "  > Instalando: $skill"
            node "$APP_ROOT/dist/index.js" skills install "$skill" --force || echo "  ! Skill $skill pulada."
        done
    fi
    echo " >>> Setup concluido!"
fi

SKILLS_REPO_DIR="$WORKSPACE_DIR/skills_repo"
SKILLS_TARGET_DIR="$WORKSPACE_DIR/skills"

echo " >>> DEBUG: A URL recebida e: '${SKILLS_GIT_REPO:-}'"
mkdir -p "$SKILLS_REPO_DIR"
mkdir -p "$SKILLS_TARGET_DIR"

if [ -n "${SKILLS_GIT_REPO:-}" ]; then
    if [ -d "$SKILLS_REPO_DIR/.git" ]; then
        echo "Atualizando repositorio de skills..."
        cd "$SKILLS_REPO_DIR"
        git fetch origin main
        git reset --hard origin/main
    else
        echo "Clonando repositorio de skills..."
        rm -rf "$SKILLS_REPO_DIR"
        git clone "$SKILLS_GIT_REPO" "$SKILLS_REPO_DIR"
    fi

    cd "$APP_ROOT"

    if [ -d "$SKILLS_REPO_DIR/skills" ]; then
        cp -r "$SKILLS_REPO_DIR/skills/"* "$SKILLS_TARGET_DIR/" 2>/dev/null || true
    else
        cp -r "$SKILLS_REPO_DIR/"* "$SKILLS_TARGET_DIR/" 2>/dev/null || true
    fi
else
    echo " >>> SKILLS_GIT_REPO vazio; pulando sincronizacao externa."
fi

wait_for_gateway() {
    local attempt=1
    local max_attempts="${1:-30}"

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
    local cron_dir="$WORKSPACE_DIR/crons"
    local current_cron_hash
    current_cron_hash="$(
        find "$cron_dir" -name "*.cron.md" -type f 2>/dev/null -exec cat {} + | sha256sum | awk '{print $1}'
    )"

    local prev_cron_hash=""
    if [ -f "$CRON_HASH_FILE" ]; then
        prev_cron_hash=$(cat "$CRON_HASH_FILE")
    fi

    if [ "$current_cron_hash" = "$prev_cron_hash" ]; then
        echo " >>> Cronjobs sem alteracao, pulando registro."
        return 0
    fi

    echo " >>> Registrando cronjobs versionados..."

    if ! ls "$cron_dir"/*.cron.md >/dev/null 2>&1; then
        echo "  ! Nenhum arquivo .cron.md encontrado em $cron_dir"
        return 0
    fi

    for cron_file in "$cron_dir"/*.cron.md; do
        local cron_id
        cron_id=$(basename "$cron_file" .cron.md)
        local cron_name
        cron_name=$(tr -d '\r' < "$cron_file" | grep -o -- '--name "[^"]*"' | head -1 | sed 's/--name "//;s/"$//')

        if [ -n "$cron_name" ] && openclaw cron list 2>/dev/null | grep -qF "\"$cron_name\""; then
            echo "  > Cronjob '$cron_name' ja existe, pulando."
            continue
        fi

        echo "  > Registrando cronjob: $cron_id"
        if ! tr -d '\r' < "$cron_file" | sh; then
            echo "  ! Erro ao registrar cronjob $cron_id."
        fi
    done

    echo "$current_cron_hash" > "$CRON_HASH_FILE"
    echo " >>> Cronjobs registrados e hash atualizado."
}

echo " >>> Subindo Gateway OpenClaw..."
node "$APP_ROOT/dist/index.js" gateway run &
GATEWAY_PID=$!

if wait_for_gateway 45; then
    register_versioned_crons
else
    echo " !!! Gateway nao ficou pronto a tempo; pulando registro de cronjobs."
fi

wait "$GATEWAY_PID"
