import fs from "node:fs";
import path from "node:path";

function getArgValue(flag) {
  const idx = process.argv.indexOf(flag);
  if (idx === -1) return null;
  const val = process.argv[idx + 1];
  if (!val || val.startsWith("--")) return null;
  return val;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`);
}

function uniq(items) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    if (!item || typeof item !== "string") continue;
    if (seen.has(item)) continue;
    seen.add(item);
    out.push(item);
  }
  return out;
}

function isModelRef(s) {
  // Expect provider/model (may contain additional slashes in model id)
  return typeof s === "string" && /^[a-z0-9][a-z0-9-]*\/.+$/i.test(s);
}

function buildAlias(modelRef) {
  const withoutUsageRouter = modelRef.replace(/^usage-router\//, "");
  const cleaned = withoutUsageRouter.replace(/^.+\//, "").replace(/:free$/i, " free");
  return cleaned;
}

function shouldWrapModels() {
  const raw = String(process.env.MODEL_USAGE_PROXY_ENABLED ?? "true").toLowerCase();
  return !["0", "false", "no", "off"].includes(raw);
}

function wrapModelRef(modelRef) {
  if (!shouldWrapModels()) return modelRef;
  if (typeof modelRef !== "string") return modelRef;
  if (modelRef.startsWith("usage-router/")) return modelRef;
  return `usage-router/${modelRef}`;
}

function normalizeProxyBaseUrl(raw) {
  const trimmed = String(raw || "http://llm-metrics-proxy:8080/openclaw").replace(/\/+$/, "");
  return trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
}

function buildModelChain(stack) {
  const lanes = stack?.policy?.lanes ?? [];
  const orderedChain = [];
  const orderedAllowlist = [];
  for (const lane of lanes) {
    const models = lane?.models ?? [];
    for (const model of models) {
      orderedAllowlist.push(model);
      if (lane?.includeInChain === false) continue;
      orderedChain.push(model);
    }
  }
  const chain = uniq(orderedChain).filter(isModelRef).map(wrapModelRef);
  if (chain.length === 0) {
    throw new Error("Model chain is empty. Check configs/model-stack.json");
  }
  const allowlist = uniq(orderedAllowlist).filter(isModelRef).map(wrapModelRef);
  return {
    primary: chain[0],
    fallbacks: chain.slice(1),
    allowlist: allowlist.length ? allowlist : chain,
  };
}

function applyToConfig(openclawConfig, chain) {
  openclawConfig.agents ??= {};
  openclawConfig.agents.defaults ??= {};
  openclawConfig.agents.defaults.model = {
    primary: chain.primary,
    fallbacks: chain.fallbacks,
  };

  // Curated allowlist for manual /model selection.
  openclawConfig.agents.defaults.models = Object.fromEntries(
    chain.allowlist.map((modelRef) => [modelRef, { alias: buildAlias(modelRef) }]),
  );

  // Keep local Ollama provider explicit; other providers are native and read keys from env/auth profiles.
  openclawConfig.models ??= {};
  openclawConfig.models.providers ??= {};
  openclawConfig.models.providers.ollama ??= {};
  openclawConfig.models.providers.ollama.baseUrl ??= "http://host.docker.internal:11434";
  openclawConfig.models.providers.ollama.apiKey ??= "ollama-local";
  openclawConfig.models.providers.ollama.api ??= "ollama";
  // Schema expects an explicit models array even if the provider resolves models dynamically.
  openclawConfig.models.providers.ollama.models ??= [];

  if (shouldWrapModels()) {
    openclawConfig.models.providers["usage-router"] ??= {};
    openclawConfig.models.providers["usage-router"].baseUrl ??=
      normalizeProxyBaseUrl(process.env.MODEL_USAGE_PROXY_URL || "http://llm-metrics-proxy:8080/openclaw");
    openclawConfig.models.providers["usage-router"].apiKey ??=
      process.env.MODEL_USAGE_PROXY_TOKEN || "usage-router-local";
    openclawConfig.models.providers["usage-router"].api ??= "openai-completions";
    openclawConfig.models.providers["usage-router"].models ??= [];
  }

  // Remove legacy custom stubs if present; prefer native providers.
  delete openclawConfig.models.providers.nvidia;
  delete openclawConfig.models.providers.openrouter;
  delete openclawConfig.models.providers.huggingface;
}

function main() {
  const cwd = process.cwd();
  const configPath =
    getArgValue("--config") ||
    process.env.OPENCLAW_CONFIG_PATH ||
    path.join(cwd, "openclaw.json");
  const stackPath =
    getArgValue("--stack") ||
    process.env.OPENCLAW_MODEL_STACK_PATH ||
    path.join(cwd, "configs", "model-stack.json");

  const stack = readJson(stackPath);
  const openclawConfig = readJson(configPath);
  const chain = buildModelChain(stack);

  applyToConfig(openclawConfig, chain);
  writeJson(configPath, openclawConfig);

  if (process.argv.includes("--print")) {
    // Minimal debug output for CI/sanity checks.
    console.log(JSON.stringify({ primary: chain.primary, fallbacks: chain.fallbacks.length }, null, 2));
  }
}

main();
