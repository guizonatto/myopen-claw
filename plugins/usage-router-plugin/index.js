import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createProviderApiKeyAuthMethod } from "openclaw/plugin-sdk/provider-auth";

import { parseUsageRouterRef } from "./src/model-ref.js";

function normalizeProxyBaseUrl(rawBaseUrl) {
  const trimmed = (rawBaseUrl || "http://llm-metrics-proxy:8080/openclaw").replace(/\/+$/, "");
  return trimmed.endsWith("/v1") ? trimmed : `${trimmed}/v1`;
}

function buildProviderRuntime() {
  return {
    baseUrl: normalizeProxyBaseUrl(process.env.MODEL_USAGE_PROXY_URL),
    apiKey: process.env.MODEL_USAGE_PROXY_TOKEN || "usage-router-local",
    api: "openai-completions",
    models: [],
  };
}

export default definePluginEntry({
  id: "usage-router",
  name: "Usage Router",
  description: "Routes model traffic through the local metrics proxy without changing OpenClaw core.",
  register(api) {
    api.registerProvider({
      id: "usage-router",
      label: "Usage Router",
      docsPath: "/providers/usage-router",
      envVars: ["MODEL_USAGE_PROXY_URL", "MODEL_USAGE_PROXY_TOKEN"],
      auth: [
        createProviderApiKeyAuthMethod({
          providerId: "usage-router",
          methodId: "api-key",
          label: "Usage Router token",
          hint: "Local token used by the usage metrics proxy",
          optionKey: "usageRouterToken",
          flagName: "--usage-router-token",
          envVar: "MODEL_USAGE_PROXY_TOKEN",
          promptMessage: "Enter the Usage Router proxy token",
          defaultModel: "usage-router/groq/llama-3.1-8b-instant",
        }),
      ],
      catalog: {
        order: "late",
        run: async () => ({
          provider: buildProviderRuntime(),
        }),
      },
      resolveDynamicModel: (ctx) => {
        const routedModelRef = String(ctx.modelId || "").startsWith("usage-router/")
          ? String(ctx.modelId)
          : `usage-router/${ctx.modelId}`;
        const parsed = parseUsageRouterRef(routedModelRef);
        return {
          id: ctx.modelId,
          name: parsed.model,
          provider: "usage-router",
          api: "openai-completions",
          baseUrl: normalizeProxyBaseUrl(process.env.MODEL_USAGE_PROXY_URL),
          reasoning: false,
          input: ["text", "image"],
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
          contextWindow: 200000,
          maxTokens: 32768,
        };
      },
    });
  },
});
