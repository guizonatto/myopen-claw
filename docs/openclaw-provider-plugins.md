Building Provider Plugins
This guide walks through building a provider plugin that adds a model provider (LLM) to OpenClaw. By the end you will have a provider with a model catalog, API key auth, and dynamic model resolution.
If you have not built any OpenClaw plugin before, read Getting Started first for the basic package structure and manifest setup.
​
Walkthrough
1
Package and manifest


package.json

openclaw.plugin.json
{
  "name": "@myorg/openclaw-acme-ai",
  "version": "1.0.0",
  "type": "module",
  "openclaw": {
    "extensions": ["./index.ts"],
    "providers": ["acme-ai"]
  }
}
The manifest declares providerAuthEnvVars so OpenClaw can detect credentials without loading your plugin runtime.
2
Register the provider

A minimal provider needs an id, label, auth, and catalog:
index.ts
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createProviderApiKeyAuthMethod } from "openclaw/plugin-sdk/provider-auth";

export default definePluginEntry({
  id: "acme-ai",
  name: "Acme AI",
  description: "Acme AI model provider",
  register(api) {
    api.registerProvider({
      id: "acme-ai",
      label: "Acme AI",
      docsPath: "/providers/acme-ai",
      envVars: ["ACME_AI_API_KEY"],

      auth: [
        createProviderApiKeyAuthMethod({
          providerId: "acme-ai",
          methodId: "api-key",
          label: "Acme AI API key",
          hint: "API key from your Acme AI dashboard",
          optionKey: "acmeAiApiKey",
          flagName: "--acme-ai-api-key",
          envVar: "ACME_AI_API_KEY",
          promptMessage: "Enter your Acme AI API key",
          defaultModel: "acme-ai/acme-large",
        }),
      ],

      catalog: {
        order: "simple",
        run: async (ctx) => {
          const apiKey =
            ctx.resolveProviderApiKey("acme-ai").apiKey;
          if (!apiKey) return null;
          return {
            provider: {
              baseUrl: "https://api.acme-ai.com/v1",
              apiKey,
              api: "openai-completions",
              models: [
                {
                  id: "acme-large",
                  name: "Acme Large",
                  reasoning: true,
                  input: ["text", "image"],
                  cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
                  contextWindow: 200000,
                  maxTokens: 32768,
                },
                {
                  id: "acme-small",
                  name: "Acme Small",
                  reasoning: false,
                  input: ["text"],
                  cost: { input: 1, output: 5, cacheRead: 0.1, cacheWrite: 1.25 },
                  contextWindow: 128000,
                  maxTokens: 8192,
                },
              ],
            },
          };
        },
      },
    });
  },
});
That is a working provider. Users can now openclaw onboard --acme-ai-api-key <key> and select acme-ai/acme-large as their model.
For bundled providers that only register one text provider with API-key auth plus a single catalog-backed runtime, prefer the narrower defineSingleProviderPluginEntry(...) helper:
import { defineSingleProviderPluginEntry } from "openclaw/plugin-sdk/provider-entry";

export default defineSingleProviderPluginEntry({
  id: "acme-ai",
  name: "Acme AI",
  description: "Acme AI model provider",
  provider: {
    label: "Acme AI",
    docsPath: "/providers/acme-ai",
    auth: [
      {
        methodId: "api-key",
        label: "Acme AI API key",
        hint: "API key from your Acme AI dashboard",
        optionKey: "acmeAiApiKey",
        flagName: "--acme-ai-api-key",
        envVar: "ACME_AI_API_KEY",
        promptMessage: "Enter your Acme AI API key",
        defaultModel: "acme-ai/acme-large",
      },
    ],
    catalog: {
      buildProvider: () => ({
        api: "openai-completions",
        baseUrl: "https://api.acme-ai.com/v1",
        models: [{ id: "acme-large", name: "Acme Large" }],
      }),
    },
  },
});
If your auth flow also needs to patch models.providers.*, aliases, and the agent default model during onboarding, use the preset helpers from openclaw/plugin-sdk/provider-onboard. The narrowest helpers are createDefaultModelPresetAppliers(...), createDefaultModelsPresetAppliers(...), and createModelCatalogPresetAppliers(...).
3
Add dynamic model resolution

If your provider accepts arbitrary model IDs (like a proxy or router), add resolveDynamicModel:
api.registerProvider({
  // ... id, label, auth, catalog from above

  resolveDynamicModel: (ctx) => ({
    id: ctx.modelId,
    name: ctx.modelId,
    provider: "acme-ai",
    api: "openai-completions",
    baseUrl: "https://api.acme-ai.com/v1",
    reasoning: false,
    input: ["text"],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 8192,
  }),
});
If resolving requires a network call, use prepareDynamicModel for async warm-up — resolveDynamicModel runs again after it completes.
4
Add runtime hooks (as needed)

Most providers only need catalog + resolveDynamicModel. Add hooks incrementally as your provider requires them.
Token exchange
Custom headers
Usage and billing
For providers that need a token exchange before each inference call:
prepareRuntimeAuth: async (ctx) => {
  const exchanged = await exchangeToken(ctx.apiKey);
  return {
    apiKey: exchanged.token,
    baseUrl: exchanged.baseUrl,
    expiresAt: exchanged.expiresAt,
  };
},
All available provider hooks

5
Add extra capabilities (optional)

A provider plugin can register speech, media understanding, image generation, and web search alongside text inference:
register(api) {
  api.registerProvider({ id: "acme-ai", /* ... */ });

  api.registerSpeechProvider({
    id: "acme-ai",
    label: "Acme Speech",
    isConfigured: ({ config }) => Boolean(config.messages?.tts),
    synthesize: async (req) => ({
      audioBuffer: Buffer.from(/* PCM data */),
      outputFormat: "mp3",
      fileExtension: ".mp3",
      voiceCompatible: false,
    }),
  });

  api.registerMediaUnderstandingProvider({
    id: "acme-ai",
    capabilities: ["image", "audio"],
    describeImage: async (req) => ({ text: "A photo of..." }),
    transcribeAudio: async (req) => ({ text: "Transcript..." }),
  });

  api.registerImageGenerationProvider({
    id: "acme-ai",
    label: "Acme Images",
    generate: async (req) => ({ /* image result */ }),
  });
}
OpenClaw classifies this as a hybrid-capability plugin. This is the recommended pattern for company plugins (one plugin per vendor). See Internals: Capability Ownership.
6
Test

src/provider.test.ts
import { describe, it, expect } from "vitest";
// Export your provider config object from index.ts or a dedicated file
import { acmeProvider } from "./provider.js";

describe("acme-ai provider", () => {
  it("resolves dynamic models", () => {
    const model = acmeProvider.resolveDynamicModel!({
      modelId: "acme-beta-v3",
    } as any);
    expect(model.id).toBe("acme-beta-v3");
    expect(model.provider).toBe("acme-ai");
  });

  it("returns catalog when key is available", async () => {
    const result = await acmeProvider.catalog!.run({
      resolveProviderApiKey: () => ({ apiKey: "test-key" }),
    } as any);
    expect(result?.provider?.models).toHaveLength(2);
  });

  it("returns null catalog when no key", async () => {
    const result = await acmeProvider.catalog!.run({
      resolveProviderApiKey: () => ({ apiKey: undefined }),
    } as any);
    expect(result).toBeNull();
  });
});
​
File structure
<bundled-plugin-root>/acme-ai/
├── package.json              # openclaw.providers metadata
├── openclaw.plugin.json      # Manifest with providerAuthEnvVars
├── index.ts                  # definePluginEntry + registerProvider
└── src/
    ├── provider.test.ts      # Tests
    └── usage.ts              # Usage endpoint (optional)
​
Catalog order reference
catalog.order controls when your catalog merges relative to built-in providers:
Order	When	Use case
simple	First pass	Plain API-key providers
profile	After simple	Providers gated on auth profiles
paired	After profile	Synthesize multiple related entries
late	Last pass	Override existing providers (wins on collision)