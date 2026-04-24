#!/bin/bash
set -euo pipefail

chown -R root:root /app/extensions 2>/dev/null || true
# docker.io + memclaw npm install movidos para o Dockerfile (build-time).

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
SKILLS_SYNC_HASH_FILE="$CONFIG_DIR/.skills_sync_version"
OBSIDIAN_MCP_VERSION_DEFAULT="1.0.6"
OBSIDIAN_MCP_VERSION_VALUE="${OBSIDIAN_MCP_VERSION:-$OBSIDIAN_MCP_VERSION_DEFAULT}"
OPENCLAW_ONBOARD_MODE_VALUE="$(echo "${OPENCLAW_ONBOARD_MODE:-once}" | tr '[:upper:]' '[:lower:]')"

mkdir -p "$CONFIG_DIR" "$WORKSPACE_DIR" "$CONFIG_DIR/hooks"
mkdir -p "$CONFIG_DIR/extensions"

# OpenClaw blocks loading plugin candidates from world-writable paths/files.
# Ensure extensions tree is never group/other-writable before running any OpenClaw command.
chmod -R go-w "$CONFIG_DIR/extensions" 2>/dev/null || true
find "$CONFIG_DIR/extensions" -type d -exec chmod 755 {} \; 2>/dev/null || true
find "$CONFIG_DIR/extensions" -type f -exec chmod 644 {} \; 2>/dev/null || true

sync_agent_workspaces() {
    for agent in leads content intel ops researcher sales-sim sindico-sim sim-control; do
        local src="$APP_ROOT/agents/${agent}"
        local dst="$CONFIG_DIR/workspace-${agent}"
        [ -d "$src" ] || continue
        mkdir -p "$dst"
        for f in SOUL.md AGENTS.md IDENTITY.md TOOLS.md; do
            [ -f "$src/$f" ] && cp "$src/$f" "$dst/$f"
        done
    done
}

sync_runtime_stack_assets() {
    mkdir -p "$WORKSPACE_DIR/configs" "$WORKSPACE_DIR/scripts"

    if [ -f "$SOURCE_WORKSPACE/configs/model-stack.json" ]; then
        cp "$SOURCE_WORKSPACE/configs/model-stack.json" "$WORKSPACE_DIR/configs/model-stack.json"
    fi
    if [ -f "$SOURCE_WORKSPACE/configs/model-limits.json" ]; then
        cp "$SOURCE_WORKSPACE/configs/model-limits.json" "$WORKSPACE_DIR/configs/model-limits.json"
    fi
    if [ -f "$SOURCE_WORKSPACE/configs/TOOLS.md" ]; then
        cp "$SOURCE_WORKSPACE/configs/TOOLS.md" "$WORKSPACE_DIR/configs/TOOLS.md"
    fi

    if [ -f "$SOURCE_WORKSPACE/scripts/apply-model-stack.mjs" ]; then
        cp "$SOURCE_WORKSPACE/scripts/apply-model-stack.mjs" "$WORKSPACE_DIR/scripts/apply-model-stack.mjs"
    fi
}

sync_versioned_cron_assets() {
    local source_cron_dir="$SOURCE_WORKSPACE/crons"
    local target_cron_dir="$WORKSPACE_DIR/crons"

    if [ ! -d "$source_cron_dir" ]; then
        return 0
    fi

    mkdir -p "$target_cron_dir"

    for source_file in "$source_cron_dir"/*.cron.md; do
        [ -f "$source_file" ] || continue
        local target_file="$target_cron_dir/$(basename "$source_file")"
        if [ ! -f "$target_file" ] || ! cmp -s "$source_file" "$target_file"; then
            cp "$source_file" "$target_file"
        fi
    done
}

apply_runtime_model_stack() {
    local config_path="$CONFIG_DIR/openclaw.json"
    local persisted_stack="$WORKSPACE_DIR/configs/model-stack.json"
    local bootstrap_stack="$SOURCE_WORKSPACE/configs/model-stack.json"
    local stack_path=""
    local script_path="$SOURCE_WORKSPACE/scripts/apply-model-stack.mjs"

    if [ -f "$persisted_stack" ]; then
        stack_path="$persisted_stack"
    elif [ -f "$bootstrap_stack" ]; then
        stack_path="$bootstrap_stack"
    fi

    if [ -n "$stack_path" ] && [ -f "$script_path" ] && [ -f "$config_path" ]; then
        node "$script_path" --config "$config_path" --stack "$stack_path" --print >/dev/null 2>&1 || true
    else
        echo " >>> [models] model stack assets missing (config=$config_path stack=$stack_path script=$script_path)"
    fi
}

sync_llm_metrics_proxy_model_limits() {
    local proxy_root="${MODEL_USAGE_PROXY_ROOT:-http://llm-metrics-proxy:8080}"
    proxy_root="${proxy_root%/}"

    if ! command -v curl >/dev/null 2>&1; then
        echo " >>> [models] curl não encontrado — pulando sync do llm-metrics-proxy."
        return 0
    fi

    if curl -fsS "$proxy_root/healthz" >/dev/null 2>&1; then
        curl -fsS -X POST "$proxy_root/admin/openclaw/sync-model-limits" >/dev/null 2>&1 || true
    fi
}

init_obsidian_vault() {
    local vault_dir="${OBSIDIAN_VAULT_PATH:-/vault}"
    local obsidian_repo="${OBSIDIAN_GIT_REPO:-}"
    local obsidian_mcp_pkg="obsidian-mcp@${OBSIDIAN_MCP_VERSION_VALUE}"

    ensure_obsidian_vault_initialized() {
        local target_dir="$1"
        local obsidian_dir="$target_dir/.obsidian"
        local app_json="$obsidian_dir/app.json"

        if [ -e "$obsidian_dir" ] && [ ! -d "$obsidian_dir" ]; then
            echo " !!! [VAULT] $obsidian_dir existe, mas não é diretório."
            return 1
        fi

        if [ ! -d "$obsidian_dir" ]; then
            echo " >>> [VAULT] .obsidian ausente — criando estrutura mínima."
            mkdir -p "$obsidian_dir"
        fi

        if [ -e "$app_json" ] && [ ! -f "$app_json" ]; then
            echo " !!! [VAULT] $app_json existe, mas não é arquivo regular."
            return 1
        fi

        if [ ! -f "$app_json" ]; then
            echo " >>> [VAULT] app.json ausente — criando arquivo mínimo."
            printf '{}\n' > "$app_json"
        fi
    }

    validate_obsidian_mcp_vault() {
        local target_dir="$1"
        local smoke_log="/tmp/obsidian-mcp-smoke.log"
        local rc=0
        local smoke_timeout="${OBSIDIAN_MCP_SMOKE_TIMEOUT_SECONDS:-45}"

        run_obsidian_smoke() {
            rc=0
            rm -f "$smoke_log"
            if command -v timeout >/dev/null 2>&1; then
                timeout "${smoke_timeout}s" npx -y "$obsidian_mcp_pkg" "$target_dir" > "$smoke_log" 2>&1 || rc=$?
            else
                npx -y "$obsidian_mcp_pkg" "$target_dir" > "$smoke_log" 2>&1 &
                local pid=$!
                sleep "$smoke_timeout"
                kill "$pid" >/dev/null 2>&1 || true
                wait "$pid" >/dev/null 2>&1 || rc=$?
            fi
        }

        run_obsidian_smoke
        if [ "$rc" != "0" ] && [ "$rc" != "124" ] && [ "$rc" != "143" ] && grep -q "Could not read package.json" "$smoke_log"; then
            echo " >>> [VAULT] Cache npx inconsistente detectado — limpando _npx e repetindo smoke test."
            rm -rf /root/.npm/_npx >/dev/null 2>&1 || true
            run_obsidian_smoke
        fi

        if [ "$rc" != "0" ] && [ "$rc" != "124" ] && [ "$rc" != "143" ]; then
            echo " !!! [VAULT] Smoke test do $obsidian_mcp_pkg falhou (exit=$rc)."
            tail -n 60 "$smoke_log" 2>/dev/null || true
            return 1
        fi

        if ! grep -q "Server initialized successfully" "$smoke_log"; then
            echo " !!! [VAULT] Smoke test não confirmou inicialização do servidor MCP."
            tail -n 60 "$smoke_log" 2>/dev/null || true
            return 1
        fi

        for required_tool in read-note create-note edit-note move-note search-vault add-tags remove-tags; do
            if ! grep -q "Registering tool: $required_tool" "$smoke_log"; then
                echo " !!! [VAULT] Tool obrigatória não registrada no smoke test: $required_tool"
                tail -n 60 "$smoke_log" 2>/dev/null || true
                return 1
            fi
        done

        echo " >>> [VAULT] Smoke test do $obsidian_mcp_pkg concluído com sucesso."
    }

    if [ -z "$obsidian_repo" ]; then
        echo " >>> [VAULT] OBSIDIAN_GIT_REPO não definido — sincronização git do vault desabilitada."
        mkdir -p "$vault_dir"
    else
        # Inject GITHUB_TOKEN into URL for auth
        local remote_url="$obsidian_repo"
        if [ -n "${GITHUB_TOKEN:-}" ] && echo "$obsidian_repo" | grep -q "github.com"; then
            remote_url="$(echo "$obsidian_repo" | sed "s|https://github.com/|https://${GITHUB_TOKEN}@github.com/|")"
        fi

        mkdir -p "$vault_dir"

        if [ ! -d "$vault_dir/.git" ]; then
            # Check if the directory has existing content (e.g. local vault files)
            if [ -n "$(ls -A "$vault_dir" 2>/dev/null)" ]; then
                echo " >>> [VAULT] Vault tem conteúdo local — inicializando git e conectando ao remoto..."
                git -C "$vault_dir" init -b main 2>/dev/null || git -C "$vault_dir" init
                git -C "$vault_dir" remote add origin "$remote_url"
                git -C "$vault_dir" fetch origin main --depth=1 2>&1 | tail -3 || true
                # Merge remote into local without overwriting (allow unrelated histories)
                git -C "$vault_dir" merge --allow-unrelated-histories -m "vault: merge remote on init" FETCH_HEAD 2>&1 | tail -5 || true
            else
                echo " >>> [VAULT] Clonando vault Obsidian de $obsidian_repo..."
                if ! git clone "$remote_url" "$vault_dir" 2>&1 | tail -3; then
                    echo " !!! [VAULT] Falha ao clonar vault — verifique OBSIDIAN_GIT_REPO e GITHUB_TOKEN."
                fi
            fi
            git -C "$vault_dir" config user.email "${GIT_USER_EMAIL:-openclaw-bot@noreply}"
            git -C "$vault_dir" config user.name "${GIT_USER_NAME:-OpenClaw Bot}"
            echo " >>> [VAULT] Vault git inicializado em $vault_dir."
        else
            echo " >>> [VAULT] Vault git já existe em $vault_dir — atualizando remote URL."
            git -C "$vault_dir" remote set-url origin "$remote_url" 2>/dev/null || true
            git -C "$vault_dir" config user.email "${GIT_USER_EMAIL:-openclaw-bot@noreply}"
            git -C "$vault_dir" config user.name "${GIT_USER_NAME:-OpenClaw Bot}"
        fi
    fi

    if ! ensure_obsidian_vault_initialized "$vault_dir"; then
        echo " !!! [VAULT] Falha no bootstrap da estrutura .obsidian."
        exit 1
    fi

    if ! validate_obsidian_mcp_vault "$vault_dir"; then
        echo " !!! [VAULT] Vault inválido para obsidian-mcp mesmo após bootstrap. Abortando startup."
        exit 1
    fi
}

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
sync_agent_workspaces
sync_runtime_stack_assets
sync_versioned_cron_assets

reconcile_openclaw_config() {
    local config_path="$CONFIG_DIR/openclaw.json"

    if [ ! -f "$config_path" ]; then
        echo " >>> Nenhum openclaw.json encontrado para reconciliar."
        return 0
    fi

    echo " >>> Reconciliando configuracao persistida do OpenClaw..."
    CONFIG_PATH="$config_path" \
    CORTEX_MEM_URL_VALUE="${CORTEX_MEM_URL:-http://cortex-mem:8085}" \
    MODEL_USAGE_PROXY_ENABLED_VALUE="${MODEL_USAGE_PROXY_ENABLED:-true}" \
    MODEL_USAGE_PROXY_ROOT_VALUE="${MODEL_USAGE_PROXY_ROOT:-http://llm-metrics-proxy:8080}" \
    MODEL_USAGE_PROXY_TOKEN_VALUE="${MODEL_USAGE_PROXY_TOKEN:-usage-router-local}" \
    OBSIDIAN_VAULT_PATH_VALUE="${OBSIDIAN_VAULT_PATH:-/vault}" \
    OBSIDIAN_MCP_VERSION_VALUE="${OBSIDIAN_MCP_VERSION_VALUE}" \
    ZAI_API_BASE_URL_VALUE="${ZAI_API_BASE_URL:-https://api.z.ai/api/paas/v4}" \
    ZAI_API_KEY_VALUE="${ZAI_API_KEY:-}" \
    ZAI_MODEL_VALUE="${ZAI_MODEL:-GLM-4.7}" \
    EMBEDDING_MODEL_VALUE="${EMBEDDING_MODEL:-qwen3-embedding:0.6b}" \
    OLLAMA_MODEL_VALUE="${OLLAMA_MODEL:-gemma4}" \
    node <<'EOF'
const fs = require("fs");

const configPath = process.env.CONFIG_PATH;
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const obsidianVaultPathRaw = String(process.env.OBSIDIAN_VAULT_PATH_VALUE || "/vault").trim();
const obsidianVaultPath = obsidianVaultPathRaw ? obsidianVaultPathRaw : "/vault";
const obsidianMcpVersionRaw = String(process.env.OBSIDIAN_MCP_VERSION_VALUE || "1.0.6").trim();
const obsidianMcpVersion = obsidianMcpVersionRaw || "1.0.6";
const obsidianMcpPackage = `obsidian-mcp@${obsidianMcpVersion}`;
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
 // Garantir que o MCP obsidian aponta para o vault correto (default: /vault).
 // (Algumas instalações antigas apontavam para ~/.openclaw/workspace e criavam um 4000-Inbox duplicado.)
 const obsidianExisting = config.mcp.servers.obsidian;
 const obsidianArgs = Array.isArray(obsidianExisting?.args) ? obsidianExisting.args.map((item) => String(item)) : [];
 const pointsToObsidianMcp =
   obsidianArgs.includes("obsidian-mcp") ||
   obsidianArgs.some((item) => item.startsWith("obsidian-mcp@"));
 const wantsNpxObsidianMcp =
   !obsidianExisting ||
   obsidianExisting.command === "npx" ||
   pointsToObsidianMcp;
 if (wantsNpxObsidianMcp) {
   config.mcp.servers.obsidian = {
     ...(typeof obsidianExisting === "object" && obsidianExisting ? obsidianExisting : {}),
     command: "npx",
     args: ["-y", obsidianMcpPackage, obsidianVaultPath],
     type: "stdio",
   };
 }
 // Garantir que o MCP de leads esteja registrado (alguns setups antigos não tinham).
 config.mcp.servers["mcp-leads"] ??= {
   command: "docker",
   args: ["exec", "-i", "mcp-leads", "python3", "/app/main.py"],
   type: "stdio",
 };

 config.plugins ??= {};
 config.plugins.slots ??= {};
 config.plugins.entries ??= {};
 config.plugins.installs ??= {};
delete config.plugins.entries["@guizonatto/openclaw-usage-router-plugin"];
delete config.plugins.installs["@guizonatto/openclaw-usage-router-plugin"];
config.plugins.slots.memory = "memclaw";
const usageProxyEnabled = !["0", "false", "no", "off"].includes(
  String(process.env.MODEL_USAGE_PROXY_ENABLED_VALUE || "true").toLowerCase()
);
const usageProxyRoot = (process.env.MODEL_USAGE_PROXY_ROOT_VALUE || "http://llm-metrics-proxy:8080").replace(/\/+$/, "");
const ollamaModelRef = `usage-router/ollama/${process.env.OLLAMA_MODEL_VALUE || "gemma4"}`;
const embeddingModelRef = `usage-router/ollama/${process.env.EMBEDDING_MODEL_VALUE}`;
config.plugins.entries.memclaw = {
  enabled: true,
  config: {
    serviceUrl: process.env.CORTEX_MEM_URL_VALUE,
    tenantId: "tenant_claw",
    autoStartServices: false,
    llmApiBaseUrl: usageProxyEnabled ? `${usageProxyRoot}/memclaw/v1` : "http://host.docker.internal:11434/v1",
    llmApiKey: usageProxyEnabled ? (process.env.MODEL_USAGE_PROXY_TOKEN_VALUE || "usage-router-local") : "ollama",
    llmModel: usageProxyEnabled ? ollamaModelRef : (process.env.OLLAMA_MODEL_VALUE || "gemma4"),
    embeddingApiBaseUrl: usageProxyEnabled ? `${usageProxyRoot}/memclaw/v1` : "http://host.docker.internal:11434/v1",
    embeddingApiKey: usageProxyEnabled ? (process.env.MODEL_USAGE_PROXY_TOKEN_VALUE || "usage-router-local") : "ollama",
    embeddingModel: usageProxyEnabled ? embeddingModelRef : process.env.EMBEDDING_MODEL_VALUE,
  },
};

config.plugins.allow = Array.from(
  new Set(
    (config.plugins.allow ?? [])
      .filter((id) => id !== "@guizonatto/openclaw-usage-router-plugin")
      .concat(["memclaw", "evolution", "usage-router"])
  )
);

const ollamaModel = process.env.OLLAMA_MODEL_VALUE || "gemma4";
// Garantir que o provider ollama usa host.docker.internal, nunca o hostname 'ollama'
config.models ??= {};
config.models.providers ??= {};
config.models.providers.ollama ??= {};
config.models.providers.ollama.baseUrl = "http://host.docker.internal:11434";
config.models.providers.ollama.apiKey ??= "ollama-local";
config.models.providers.ollama.api ??= "ollama";
if (usageProxyEnabled) {
  config.models.providers["usage-router"] ??= {};
  config.models.providers["usage-router"].baseUrl = `${usageProxyRoot}/openclaw/v1`;
  config.models.providers["usage-router"].apiKey = process.env.MODEL_USAGE_PROXY_TOKEN_VALUE || "usage-router-local";
  config.models.providers["usage-router"].api = "openai-completions";
  config.models.providers["usage-router"].models ??= [];
}
config.agents ??= {};
config.agents.defaults ??= {};
config.agents.defaults.memorySearch = { enabled: false };
// Default model stack is applied by scripts/apply-model-stack.mjs (runs after reconcile).
config.agents.defaults.model ??= { primary: `ollama/${ollamaModel}`, fallbacks: [] };
const desiredAgents = [
  {
    id: "default",
    default: true,
    workspace: "~/.openclaw/workspace",
    subagents: { allowAgents: ["librarian"] },
  },
  {
    id: "leads",
    name: "Prospector",
    workspace: "~/.openclaw/workspace-leads",
    tools: {
      allow: ["exec", "read", "cron", "sessions_list"],
      deny: ["browser", "canvas", "write", "edit"],
    },
  },
  {
    id: "content",
    name: "Copywriter",
    workspace: "~/.openclaw/workspace-content",
    tools: {
      allow: ["exec", "read", "web_search", "web_fetch", "browser", "cron"],
    },
  },
  {
    id: "intel",
    name: "Sentinel",
    workspace: "~/.openclaw/workspace-intel",
    tools: {
      allow: ["exec", "read", "web_search", "web_fetch", "cron"],
      deny: ["browser", "canvas"],
    },
  },
  {
    id: "ops",
    name: "Steward",
    workspace: "~/.openclaw/workspace-ops",
    tools: {
      allow: ["exec", "read", "cron"],
      deny: ["browser", "canvas", "write", "edit"],
    },
  },
  {
    id: "usell",
    name: "Usell Sales",
    workspace: "~/.openclaw/workspace",
    tools: { profile: "messaging" },
  },
  {
    id: "librarian",
    name: "Librarian",
    workspace: "/vault",
  },
];
const existingAgents = Array.isArray(config.agents.list) ? config.agents.list : [];
const existingById = new Map(
  existingAgents
    .filter((agent) => agent && typeof agent === "object" && typeof agent.id === "string")
    .map((agent) => [agent.id, agent]),
);
const mergedAgents = [];
for (const desiredAgent of desiredAgents) {
  const existingAgent = existingById.get(desiredAgent.id) || {};
  const mergedAgent = { ...existingAgent, ...desiredAgent };
  if (desiredAgent.tools) {
    mergedAgent.tools = { ...(existingAgent.tools || {}), ...desiredAgent.tools };
  }
  if (desiredAgent.subagents) {
    const existingAllow = Array.isArray(existingAgent.subagents?.allowAgents) ? existingAgent.subagents.allowAgents : [];
    const desiredAllow = Array.isArray(desiredAgent.subagents?.allowAgents) ? desiredAgent.subagents.allowAgents : [];
    mergedAgent.subagents = {
      ...(existingAgent.subagents || {}),
      ...(desiredAgent.subagents || {}),
      allowAgents: Array.from(new Set([...existingAllow, ...desiredAllow])),
    };
  }
  mergedAgents.push(mergedAgent);
  existingById.delete(desiredAgent.id);
}
for (const leftover of existingById.values()) {
  mergedAgents.push(leftover);
}
for (const agent of mergedAgents) {
  if (agent && typeof agent === "object" && typeof agent.id === "string") {
    agent.default = agent.id === "default";
  }
}
config.agents.list = mergedAgents;
  config.tools ??= {};
  config.tools.web ??= {};
  config.tools.web.fetch ??= {};
  config.tools.web.fetch.enabled = true;
  config.tools.web.search ??= {};
  const globalSearchProvider = String(process.env.GLOBAL_WEB_SEARCH_PROVIDER || "").trim();
  const legacySearchProvider = String(process.env.WEB_SEARCH_PROVIDER || "").trim();
  const requestedSearchProvider = String(
    globalSearchProvider && globalSearchProvider.toLowerCase() !== "duckduckgo"
      ? globalSearchProvider
      : legacySearchProvider || globalSearchProvider || "duckduckgo",
  )
    .trim()
    .toLowerCase();
  const hasKey = (name) => Boolean(String(process.env[name] || "").trim());
  const canUseSearchProvider = (provider) => {
    switch (provider) {
      case "duckduckgo":
        return true;
      case "tavily":
        return hasKey("TAVILY_API_KEY");
      case "brave":
        return hasKey("BRAVE_API_KEY") || hasKey("BRAVE_API_KEYS");
      case "firecrawl":
        return hasKey("FIRECRAWL_API_KEY");
      default:
        return true;
    }
  };
  const effectiveSearchProvider = canUseSearchProvider(requestedSearchProvider)
    ? requestedSearchProvider
    : "duckduckgo";
  config.tools.web.search.provider = effectiveSearchProvider;
config.skills ??= {};
config.skills.entries ??= {};
config.skills.entries["tech-news-digest"] ??= {};
config.skills.entries["tech-news-digest"].env ??= {};
if (process.env.TAVILY_API_KEY) {
  config.skills.entries["tech-news-digest"].env.WEB_SEARCH_BACKEND = "tavily";
} else {
  delete config.skills.entries["tech-news-digest"].env.WEB_SEARCH_BACKEND;
}

config.channels ??= {};
if (String(process.env.DISCORD_BOT_TOKEN || "").trim()) {
  const discordGuildId = String(process.env.DISCORD_GUILD_ID || "").trim();
  const discordChannelId = String(process.env.DISCORD_ZIND_CONTENT_CHANNEL_ID || process.env.DISCORD_CHANNEL_ID || "").trim();
  config.channels.discord ??= {};
  config.channels.discord.enabled = true;
  config.channels.discord.token = { source: "env", provider: "default", id: "DISCORD_BOT_TOKEN" };
  config.channels.discord.allowFrom = ["*"];
  config.channels.discord.dmPolicy = "open";
  config.channels.discord.groupPolicy ??= "open";

  if (discordGuildId) {
    config.channels.discord.guilds ??= {};
    const guildEntry =
      typeof config.channels.discord.guilds[discordGuildId] === "object" && config.channels.discord.guilds[discordGuildId]
        ? config.channels.discord.guilds[discordGuildId]
        : {};
    guildEntry.requireMention = false;

    if (discordChannelId) {
      guildEntry.channels ??= {};
      const channelEntry =
        typeof guildEntry.channels[discordChannelId] === "object" && guildEntry.channels[discordChannelId]
          ? guildEntry.channels[discordChannelId]
          : {};
      channelEntry.requireMention = false;
      guildEntry.channels[discordChannelId] = channelEntry;
    }

    config.channels.discord.guilds[discordGuildId] = guildEntry;
  }
}

if (config.channels?.discord?.guilds && typeof config.channels.discord.guilds === "object") {
  for (const guildEntry of Object.values(config.channels.discord.guilds)) {
    if (!guildEntry || typeof guildEntry !== "object") continue;
    if (!guildEntry.channels || typeof guildEntry.channels !== "object") continue;
    for (const channelEntry of Object.values(guildEntry.channels)) {
      if (channelEntry && typeof channelEntry === "object") {
        delete channelEntry.allowed;
      }
    }
  }
}

config.gateway ??= {};
config.gateway.controlUi ??= {};
const origins = new Set(config.gateway.controlUi.allowedOrigins ?? []);
["http://localhost:8090"].forEach(o => origins.add(o));
config.gateway.controlUi.allowedOrigins = Array.from(origins);

fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`);
EOF
}

init_obsidian_vault
reconcile_openclaw_config

# Log provider selection (helps debug WEB_SEARCH_PROVIDER vs GLOBAL_WEB_SEARCH_PROVIDER precedence)
if command -v node >/dev/null 2>&1 && [ -f "$CONFIG_DIR/openclaw.json" ]; then
    WEB_SEARCH_EFFECTIVE="$(
        node -e "const fs=require('fs');try{const cfg=JSON.parse(fs.readFileSync('$CONFIG_DIR/openclaw.json','utf8'));const p=(((cfg.tools||{}).web||{}).search||{}).provider||'';process.stdout.write(String(p));}catch(e){}" 2>/dev/null || true
    )"
    if [ -n "${WEB_SEARCH_EFFECTIVE:-}" ]; then
        REQUESTED_WEB_SEARCH_PROVIDER="${GLOBAL_WEB_SEARCH_PROVIDER:-}"
        if [ -z "${REQUESTED_WEB_SEARCH_PROVIDER:-}" ] || [ "${REQUESTED_WEB_SEARCH_PROVIDER}" = "duckduckgo" ]; then
            REQUESTED_WEB_SEARCH_PROVIDER="${WEB_SEARCH_PROVIDER:-${REQUESTED_WEB_SEARCH_PROVIDER:-duckduckgo}}"
        fi
        TAVILY_KEY_STATUS="missing"
        [ -n "${TAVILY_API_KEY:-}" ] && TAVILY_KEY_STATUS="set"
        echo " >>> [web_search] provider=${WEB_SEARCH_EFFECTIVE} (requested=${REQUESTED_WEB_SEARCH_PROVIDER} tavily_key=${TAVILY_KEY_STATUS})"
    fi
    unset WEB_SEARCH_EFFECTIVE REQUESTED_WEB_SEARCH_PROVIDER TAVILY_KEY_STATUS
fi

# Apply repo-tracked model stack after reconciliation so restarts don't revert to legacy defaults.
apply_runtime_model_stack
sync_llm_metrics_proxy_model_limits
init_git_staging

if [ "${OPENCLAW_DOCTOR:-0}" = "1" ]; then
    echo " >>> Reparando configuracao (doctor --fix)..."
    node "$APP_ROOT/dist/index.js" doctor --fix 2>/dev/null || true
fi

# Model + provider config already applied by reconcile_openclaw_config() above.

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
case "$OPENCLAW_ONBOARD_MODE_VALUE" in
    once|first|first-boot)
        if [ ! -f "$USER_VERSION_FILE" ] || [ ! -f "$ONBOARD_HASH_FILE" ]; then
            echo "Onboarding mode=once and markers missing. Running onboarding once..."
            NEEDS_ONBOARDING=1
        else
            echo "Onboarding mode=once and markers found. Skipping onboarding."
        fi
        ;;
    auto|hash)
        if [ "$USER_VERSION" != "$PREV_USER_VERSION" ]; then
            echo "USER.md version changed. Forcing onboarding (mode=auto)..."
            NEEDS_ONBOARDING=1
        elif [ "$CURRENT_HASH" != "$PREV_HASH" ]; then
            echo "Onboarding changes detected. Running onboarding (mode=auto)..."
            NEEDS_ONBOARDING=1
        else
            echo "No onboarding changes detected (mode=auto). Skipping onboarding."
        fi
        ;;
    force|always)
        echo "Onboarding mode=force. Running onboarding."
        NEEDS_ONBOARDING=1
        ;;
    off|disabled|never|manual)
        echo "Onboarding mode=$OPENCLAW_ONBOARD_MODE_VALUE. Skipping onboarding."
        ;;
    *)
        echo "Unknown OPENCLAW_ONBOARD_MODE='$OPENCLAW_ONBOARD_MODE_VALUE'. Using mode=once fallback."
        if [ ! -f "$USER_VERSION_FILE" ] || [ ! -f "$ONBOARD_HASH_FILE" ]; then
            NEEDS_ONBOARDING=1
        fi
        ;;
esac

EVOLUTION_PLUGIN_DIR="/root/.openclaw/extensions/evolution"
EVOLUTION_PLUGIN_TGZ="/app/plugins/guizonatto-evolution-plugin-1.0.0.tgz"
USAGE_ROUTER_PLUGIN_SRC="/app/plugins/usage-router-plugin"

fix_world_writable_plugin_dir() {
    local dir="$1"
    if [ -z "$dir" ] || [ ! -d "$dir" ]; then
        return 0
    fi

    # OpenClaw blocks loading plugin candidates from world-writable paths.
    # Ensure group/other are not writable.
    chmod -R go-w "$dir" 2>/dev/null || true
    find "$dir" -type d -exec chmod 755 {} \; 2>/dev/null || true
    find "$dir" -type f -exec chmod 644 {} \; 2>/dev/null || true
}

find_installed_usage_router_dir() {
    # When installing from a local folder, OpenClaw may create a hashed extension dir name like:
    # /root/.openclaw/extensions/@guizonatto-openclaw-usage-router-plugin-<hash>
    local candidates
    candidates="$(find /root/.openclaw/extensions -maxdepth 1 -type d -name '@guizonatto-openclaw-usage-router-plugin-*' 2>/dev/null | head -1 || true)"
    if [ -n "$candidates" ]; then
        echo "$candidates"
        return 0
    fi

    if [ -d "/root/.openclaw/extensions/usage-router" ]; then
        echo "/root/.openclaw/extensions/usage-router"
        return 0
    fi

    echo ""
}

sync_usage_router_plugin_files() {
    local installed_dir="$1"
    if [ -z "$installed_dir" ] || [ ! -d "$installed_dir" ]; then
        return 0
    fi
    if [ ! -d "$USAGE_ROUTER_PLUGIN_SRC" ]; then
        return 0
    fi

    # Keep the installed extension in sync with the repo copy. This avoids stale manifests
    # (e.g. missing 'id') causing gateway config validation to fail.
    cp "$USAGE_ROUTER_PLUGIN_SRC/openclaw.plugin.json" "$installed_dir/openclaw.plugin.json" 2>/dev/null || true
    cp "$USAGE_ROUTER_PLUGIN_SRC/index.js" "$installed_dir/index.js" 2>/dev/null || true
    rm -rf "$installed_dir/src" 2>/dev/null || true
    cp -r "$USAGE_ROUTER_PLUGIN_SRC/src" "$installed_dir/src" 2>/dev/null || true
}

if [ ! -d "$EVOLUTION_PLUGIN_DIR" ] && [ -f "$EVOLUTION_PLUGIN_TGZ" ]; then
    echo " >>> Instalando plugin Evolution..."
    node "$APP_ROOT/dist/index.js" plugins install "$EVOLUTION_PLUGIN_TGZ" --dangerously-force-unsafe-install
fi

USAGE_ROUTER_INSTALLED_DIR="$(find_installed_usage_router_dir)"
if [ -n "$USAGE_ROUTER_INSTALLED_DIR" ]; then
    fix_world_writable_plugin_dir "$USAGE_ROUTER_INSTALLED_DIR"
    sync_usage_router_plugin_files "$USAGE_ROUTER_INSTALLED_DIR"
    fix_world_writable_plugin_dir "$USAGE_ROUTER_INSTALLED_DIR"
else
    if [ -d "$USAGE_ROUTER_PLUGIN_SRC" ]; then
        echo " >>> Instalando plugin Usage Router..."
        node "$APP_ROOT/dist/index.js" plugins install "$USAGE_ROUTER_PLUGIN_SRC" --dangerously-force-unsafe-install || true

        USAGE_ROUTER_INSTALLED_DIR="$(find_installed_usage_router_dir)"
        if [ -n "$USAGE_ROUTER_INSTALLED_DIR" ]; then
            fix_world_writable_plugin_dir "$USAGE_ROUTER_INSTALLED_DIR"
            sync_usage_router_plugin_files "$USAGE_ROUTER_INSTALLED_DIR"
            fix_world_writable_plugin_dir "$USAGE_ROUTER_INSTALLED_DIR"
        fi
    fi
fi

# plugins.allow already set by reconcile_openclaw_config().

echo " >>> [DEBUG] Checando Variaveis..."
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo " !!! ERRO: TELEGRAM_BOT_TOKEN VAZIO."
    exit 1
fi
echo " > Telegram Token OK."

if [ "$NEEDS_ONBOARDING" = "1" ]; then
    echo " >>> [ETAPA 1/5] Iniciando Onboarding..."
    API_KEY_VALUE=""
    AUTH_CHOICE=""
    for AUTH_CHOICE_CANDIDATE in \
        groq-api-key \
        gemini-api-key \
        google-api-key \
        mistral-api-key \
        cerebras-api-key \
        qwen-api-key \
        deepseek-api-key \
        openrouter-api-key \
        zai-api-key \
        openai-codex
    do
        case "$AUTH_CHOICE_CANDIDATE" in
            groq-api-key) VAL="${GROQ_API_KEY:-}" ;;
            gemini-api-key) VAL="${GEMINI_API_KEY:-}" ;;
            google-api-key) VAL="${GOOGLE_API_KEY:-}" ;;
            mistral-api-key) VAL="${MISTRAL_API_KEY:-}" ;;
            cerebras-api-key) VAL="${CEREBRAS_API_KEY:-}" ;;
            qwen-api-key) VAL="${QWEN_API_KEY:-}" ;;
            deepseek-api-key) VAL="${DEEPSEEK_API_KEY:-}" ;;
            openrouter-api-key) VAL="${OPENROUTER_API_KEY:-}" ;;
            zai-api-key) VAL="${ZAI_API_KEY:-}" ;;
            openai-codex) VAL="${OPENAI_CODEX:-}" ;;
            *) VAL="" ;;
        esac

        if [ -n "$VAL" ]; then
            AUTH_CHOICE="$AUTH_CHOICE_CANDIDATE"
            API_KEY_VALUE="$VAL"
            echo "Usando provider: $AUTH_CHOICE_CANDIDATE"
            break
        fi
    done

    if [ -z "$API_KEY_VALUE" ]; then
        echo " !!! ERRO: Nenhuma chave de API encontrada para providers suportados (groq, gemini/google, mistral, cerebras, qwen, deepseek, openrouter, zai, openai-codex)."
        exit 1
    fi

    echo ">>> AI MODEL: $AUTH_CHOICE"

    ONBOARD_ARGS=(
        --non-interactive
        --accept-risk
        --gateway-bind "$GATEWAY_BIND"
        --gateway-auth password
        --gateway-password "$ADMIN_PASSWORD"
        --skip-channels
        --skip-health
    )

    case "$AUTH_CHOICE" in
        groq-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider groq --token "$API_KEY_VALUE")
            ;;
        gemini-api-key|google-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider google --token "$API_KEY_VALUE")
            ;;
        mistral-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider mistral --token "$API_KEY_VALUE")
            ;;
        cerebras-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider cerebras --token "$API_KEY_VALUE")
            ;;
        qwen-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider qwen --token "$API_KEY_VALUE")
            ;;
        deepseek-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider deepseek --token "$API_KEY_VALUE")
            ;;
        openrouter-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider openrouter --token "$API_KEY_VALUE")
            ;;
        zai-api-key)
            ONBOARD_ARGS+=(--auth-choice apiKey --token-provider zai --token "$API_KEY_VALUE")
            ;;
        openai-codex)
            ONBOARD_ARGS+=(--auth-choice openai-codex --openai-codex "$API_KEY_VALUE")
            ;;
        *)
            echo " !!! ERRO: auth choice nao suportado para onboarding: $AUTH_CHOICE"
            exit 1
            ;;
    esac

    node "$APP_ROOT/dist/index.js" onboard "${ONBOARD_ARGS[@]}"

    echo "$USER_VERSION" > "$USER_VERSION_FILE"
    echo "$CURRENT_HASH" > "$ONBOARD_HASH_FILE"
    echo "Onboarding version/hash atualizados."

    echo " >>> [ETAPA 2/5] Ajustando Sandboxing, Browser e Ollama..."
    [ "${ENABLE_SANDBOX:-}" = "true" ] && node "$APP_ROOT/dist/index.js" config set agents.defaults.sandbox.mode "non-main"
    node "$APP_ROOT/dist/index.js" config set tools.web.fetch.enabled true --strict-json
    WEB_SEARCH_PROVIDER_LEGACY="${WEB_SEARCH_PROVIDER:-}"
    WEB_SEARCH_PROVIDER="${GLOBAL_WEB_SEARCH_PROVIDER:-duckduckgo}"
    if [ "${WEB_SEARCH_PROVIDER}" = "duckduckgo" ] && [ -n "${WEB_SEARCH_PROVIDER_LEGACY}" ]; then
        WEB_SEARCH_PROVIDER="${WEB_SEARCH_PROVIDER_LEGACY}"
    fi
    if [ "${WEB_SEARCH_PROVIDER}" = "tavily" ] && [ -z "${TAVILY_API_KEY:-}" ]; then
        WEB_SEARCH_PROVIDER="duckduckgo"
    fi
    if [ "${WEB_SEARCH_PROVIDER}" = "brave" ] && [ -z "${BRAVE_API_KEY:-}" ] && [ -z "${BRAVE_API_KEYS:-}" ]; then
        WEB_SEARCH_PROVIDER="duckduckgo"
    fi
    if [ "${WEB_SEARCH_PROVIDER}" = "firecrawl" ] && [ -z "${FIRECRAWL_API_KEY:-}" ]; then
        WEB_SEARCH_PROVIDER="duckduckgo"
    fi
    node "$APP_ROOT/dist/index.js" config set tools.web.search.provider "${WEB_SEARCH_PROVIDER}"
    node "$APP_ROOT/dist/index.js" config set browser.enabled true --strict-json

    if [ -n "${TAVILY_API_KEY:-}" ]; then
        node "$APP_ROOT/dist/index.js" config set skills.entries.tech-news-digest.env.WEB_SEARCH_BACKEND "tavily"
    fi

    echo "  > Mantendo Ollama configurado como provider local..."
    node "$APP_ROOT/dist/index.js" config set models.providers.ollama.apiKey "${OLLAMA_API_KEY:-ollama-local}"
    node "$APP_ROOT/dist/index.js" config set models.providers.ollama.baseUrl "http://host.docker.internal:11434"
    node "$APP_ROOT/dist/index.js" config set models.providers.ollama.api "ollama"

    echo "  > Reaplicando model stack (policy) após onboarding..."
    sync_runtime_stack_assets
    apply_runtime_model_stack

    echo " >>> [ETAPA 3/5] Conectando Telegram..."
    node "$APP_ROOT/dist/index.js" channels add --channel telegram --token "$TELEGRAM_BOT_TOKEN"
    node "$APP_ROOT/dist/index.js" config set channels.telegram.allowFrom "[\"$TELEGRAM_USER_ID\"]" --strict-json
    node "$APP_ROOT/dist/index.js" config set channels.telegram.dmPolicy "allowlist"

    if [ -n "${DISCORD_BOT_TOKEN:-}" ]; then
        echo " >>> [ETAPA 3.1/5] Conectando Discord..."
        node "$APP_ROOT/dist/index.js" config set channels.discord.token \
            --ref-provider default --ref-source env --ref-id DISCORD_BOT_TOKEN
        node "$APP_ROOT/dist/index.js" config set channels.discord.enabled true --strict-json
        node "$APP_ROOT/dist/index.js" config set channels.discord.allowFrom '["*"]' --strict-json
        node "$APP_ROOT/dist/index.js" config set channels.discord.dmPolicy '"open"' --strict-json
        node "$APP_ROOT/dist/index.js" config set channels.discord.groupPolicy '"open"' --strict-json
        if [ -n "${DISCORD_GUILD_ID:-}" ]; then
            node "$APP_ROOT/dist/index.js" config set channels.discord.guilds."${DISCORD_GUILD_ID}".requireMention false --strict-json
            if [ -n "${DISCORD_ZIND_CONTENT_CHANNEL_ID:-}" ]; then
                node "$APP_ROOT/dist/index.js" config set channels.discord.guilds."${DISCORD_GUILD_ID}".channels."${DISCORD_ZIND_CONTENT_CHANNEL_ID}".requireMention false --strict-json
            fi
        fi
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
    OBSIDIAN_VAULT_DIR="${OBSIDIAN_VAULT_PATH:-/vault}"
    OBSIDIAN_MCP_PACKAGE="obsidian-mcp@${OBSIDIAN_MCP_VERSION_VALUE}"
    node "$APP_ROOT/dist/index.js" config set mcp.servers.obsidian.args "[\"-y\",\"${OBSIDIAN_MCP_PACKAGE}\",\"${OBSIDIAN_VAULT_DIR}\"]" --strict-json

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
    # Compute remote HEAD hash without a full fetch
    REMOTE_SKILLS_HASH="$(git ls-remote "$SKILLS_GIT_REPO" refs/heads/main 2>/dev/null | awk '{print $1}')"
    PREV_SKILLS_HASH=""
    if [ -f "$SKILLS_SYNC_HASH_FILE" ]; then
        PREV_SKILLS_HASH=$(cat "$SKILLS_SYNC_HASH_FILE")
    fi

    if [ -n "$REMOTE_SKILLS_HASH" ] && [ "$REMOTE_SKILLS_HASH" = "$PREV_SKILLS_HASH" ]; then
        echo " >>> Skills repo sem alteracao, pulando sincronizacao."
    else
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

        [ -n "$REMOTE_SKILLS_HASH" ] && echo "$REMOTE_SKILLS_HASH" > "$SKILLS_SYNC_HASH_FILE"
    fi
else
    echo " >>> SKILLS_GIT_REPO vazio; pulando sincronizacao externa."
fi

wait_for_gateway() {
    local attempt=1
    local max_attempts="${1:-30}"

    while [ "$attempt" -le "$max_attempts" ]; do
        if curl -sf http://127.0.0.1:18789/healthz >/dev/null 2>&1; then
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
    local cron_hash_dir="$CONFIG_DIR/cron/source-hashes"
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
    mkdir -p "$cron_hash_dir"

    if ! ls "$cron_dir"/*.cron.md >/dev/null 2>&1; then
        echo "  ! Nenhum arquivo .cron.md encontrado em $cron_dir"
        return 0
    fi

    find_cron_jobs_by_name() {
        local target_name="$1"
        local jobs_file="$CONFIG_DIR/cron/jobs.json"

        if [ -z "$target_name" ] || [ ! -f "$jobs_file" ]; then
            return 0
        fi

        python3 - "$jobs_file" "$target_name" <<'PY'
import json
import sys

jobs_path, target_name = sys.argv[1], sys.argv[2]

try:
    with open(jobs_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    raise SystemExit(0)

def walk(node):
    if isinstance(node, dict):
        name = node.get("name")
        if name == target_name:
            value = node.get("jobId")
            if not isinstance(value, str) or not value:
                value = node.get("id")
            if isinstance(value, str) and value:
                agent = node.get("agentId")
                if not isinstance(agent, str):
                    agent = ""
                print(f"{value}|{agent}")
        for child in node.values():
            walk(child)
    elif isinstance(node, list):
        for child in node:
            walk(child)

walk(payload)
PY
    }

    extract_agent_from_cron_command() {
        local raw_command="$1"
        python3 - "$raw_command" <<'PY'
import shlex
import sys

if len(sys.argv) < 2:
    raise SystemExit(0)

raw = sys.argv[1]
try:
    tokens = shlex.split(raw)
except Exception:
    print("")
    raise SystemExit(0)

agent = ""
for idx, token in enumerate(tokens[:-1]):
    if token == "--agent":
        agent = tokens[idx + 1]

print(agent)
PY
    }

    for cron_file in "$cron_dir"/*.cron.md; do
        local cron_id
        cron_id=$(basename "$cron_file" .cron.md)
        local cron_name
        cron_name=$(tr -d '\r' < "$cron_file" | grep -o -- '--name "[^"]*"' | head -1 | sed 's/--name "//;s/"$//')
        local cron_command
        local cron_file_hash
        local cron_hash_file
        local prev_cron_file_hash=""
        local desired_agent=""
        local expected_existing_agent=""
        local existing_job_id=""
        local existing_job_entries=""
        local existing_job_agent=""
        local recreate_for_agent_mismatch=0

        cron_file_hash="$(sha256sum "$cron_file" | awk '{print $1}')"
        cron_hash_file="$cron_hash_dir/$cron_id.sha256"
        if [ -f "$cron_hash_file" ]; then
            prev_cron_file_hash="$(cat "$cron_hash_file")"
        fi

        cron_command="$(tr -d '\r' < "$cron_file")"
        desired_agent="$(extract_agent_from_cron_command "$cron_command")"

        if [ -n "$cron_name" ]; then
            existing_job_entries="$(find_cron_jobs_by_name "$cron_name")"
            existing_job_id="$(printf '%s\n' "$existing_job_entries" | awk -F'|' 'NF{last=$1} END{print last}')"
            existing_job_agent="$(printf '%s\n' "$existing_job_entries" | awk -F'|' 'NF{last=$2} END{print last}')"
        fi

        expected_existing_agent="${desired_agent:-default}"
        if [ -n "$existing_job_id" ]; then
            local normalized_existing_agent="${existing_job_agent:-default}"
            if [ "$normalized_existing_agent" != "$expected_existing_agent" ]; then
                recreate_for_agent_mismatch=1
                echo "  > Cronjob '$cron_name' com agent incorreto (atual=${normalized_existing_agent}, esperado=${expected_existing_agent}); forçando recriação."
            fi
        fi

        if [ -n "$existing_job_id" ] && [ -z "$prev_cron_file_hash" ] && [ "$recreate_for_agent_mismatch" -eq 0 ]; then
            case "$cron_id" in
                obsidian_git_push|obsidian_git_pull)
                    ;;
                *)
                    echo "  > Cronjob '$cron_name' ja existente (migração inicial), registrando hash local e pulando."
                    echo "$cron_file_hash" > "$cron_hash_file"
                    continue
                    ;;
            esac
        fi

        if [ -n "$existing_job_id" ] && [ "$cron_file_hash" = "$prev_cron_file_hash" ] && [ "$recreate_for_agent_mismatch" -eq 0 ]; then
            echo "  > Cronjob '$cron_name' sem alteracao, pulando."
            continue
        fi

        if [ -n "$existing_job_id" ]; then
            echo "  > Cronjob '$cron_name' alterado, recriando..."
            while IFS='|' read -r stale_job_id _; do
                [ -n "$stale_job_id" ] || continue
                if ! openclaw cron remove "$stale_job_id" >/dev/null 2>&1; then
                    echo "  ! Falha ao remover cronjob '$cron_name' (id: $stale_job_id); tentando registrar mesmo assim."
                fi
            done <<<"$existing_job_entries"
        else
            echo "  > Registrando cronjob: $cron_id"
        fi

        if [ -n "$cron_name" ]; then
            cron_command="$(
                python3 -c 'import re, sys, urllib.parse
name = urllib.parse.quote(sys.argv[1], safe="")
command = sys.stdin.read()
marker = f"[telemetry trigger_type=cron trigger_name={name}] "
print(re.sub(r"--message \"([^\"]*)\"", lambda m: f"--message \"{marker}{m.group(1)}\"", command, count=1), end="")' \
                "$cron_name" <<<"$cron_command"
            )"
        fi
        if ! printf '%s\n' "$cron_command" | sh; then
            echo "  ! Erro ao registrar cronjob $cron_id."
            continue
        fi
        echo "$cron_file_hash" > "$cron_hash_file"
    done

    echo "$current_cron_hash" > "$CRON_HASH_FILE"
    echo " >>> Cronjobs registrados e hash atualizado."
}

seed_memclaw_config() {
    local cfg_dir="/root/.local/share/memclaw"
    local cfg_file="$cfg_dir/config.toml"
    if [ -f "$cfg_file" ]; then
        return 0
    fi
    mkdir -p "$cfg_dir"
    local ollama_model="${OLLAMA_MODEL:-gemma4}"
    local embed_model="${EMBEDDING_MODEL:-qwen3-embedding:0.6b}"
    cat > "$cfg_file" <<TOML
[qdrant]
url = "http://qdrant:6334"
collection_name = "cortex_memories"
timeout_secs = 30

[llm]
api_base_url = "http://host.docker.internal:11434/v1"
api_key = "ollama"
model_efficient = "$ollama_model"
temperature = 0.1
max_tokens = 65536

[embedding]
api_base_url = "http://host.docker.internal:11434/v1"
api_key = "ollama"
model_name = "$embed_model"
batch_size = 10
timeout_secs = 30

[server]
host = "0.0.0.0"
port = 8085
cors_origins = ["*"]

[logging]
enabled = false
log_directory = "logs"
level = "info"
TOML
    echo " >>> [memclaw] config.toml pre-seeded (ollama/$ollama_model)"
}

seed_memclaw_config

echo " >>> Subindo Gateway OpenClaw..."
node "$APP_ROOT/dist/index.js" gateway run &
GATEWAY_PID=$!

if wait_for_gateway 45; then
    register_versioned_crons
else
    echo " !!! Gateway nao ficou pronto a tempo; pulando registro de cronjobs."
fi

wait "$GATEWAY_PID"
