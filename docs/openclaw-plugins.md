Plugins
Plugins extend OpenClaw with new capabilities: channels, model providers, tools, skills, speech, image generation, and more. Some plugins are core (shipped with OpenClaw), others are external (published on npm by the community).
​
Quick start
1
See what is loaded

openclaw plugins list
2
Install a plugin

# From npm
openclaw plugins install @openclaw/voice-call

# From a local directory or archive
openclaw plugins install ./my-plugin
openclaw plugins install ./my-plugin.tgz
3
Restart the Gateway

openclaw gateway restart
Then configure under plugins.entries.\<id\>.config in your config file.
If you prefer chat-native control, enable commands.plugins: true and use:
/plugin install clawhub:@openclaw/voice-call
/plugin show voice-call
/plugin enable voice-call
The install path uses the same resolver as the CLI: local path/archive, explicit clawhub:<pkg>, or bare package spec (ClawHub first, then npm fallback).
​
Plugin types
OpenClaw recognizes two plugin formats:
Format	How it works	Examples
Native	openclaw.plugin.json + runtime module; executes in-process	Official plugins, community npm packages
Bundle	Codex/Claude/Cursor-compatible layout; mapped to OpenClaw features	.codex-plugin/, .claude-plugin/, .cursor-plugin/
Both show up under openclaw plugins list. See Plugin Bundles for bundle details.
If you are writing a native plugin, start with Building Plugins and the Plugin SDK Overview.
​
Official plugins
​
Installable (npm)
Plugin	Package	Docs
Matrix	@openclaw/matrix	Matrix
Microsoft Teams	@openclaw/msteams	Microsoft Teams
Nostr	@openclaw/nostr	Nostr
Voice Call	@openclaw/voice-call	Voice Call
Zalo	@openclaw/zalo	Zalo
Zalo Personal	@openclaw/zalouser	Zalo Personal
​
Core (shipped with OpenClaw)
Model providers (enabled by default)

Memory plugins

Speech providers (enabled by default)

Other

Looking for third-party plugins? See Community Plugins.
​
Configuration
{
  plugins: {
    enabled: true,
    allow: ["voice-call"],
    deny: ["untrusted-plugin"],
    load: { paths: ["~/Projects/oss/voice-call-extension"] },
    entries: {
      "voice-call": { enabled: true, config: { provider: "twilio" } },
    },
  },
}
Field	Description
enabled	Master toggle (default: true)
allow	Plugin allowlist (optional)
deny	Plugin denylist (optional; deny wins)
load.paths	Extra plugin files/directories
slots	Exclusive slot selectors (e.g. memory, contextEngine)
entries.\<id\>	Per-plugin toggles + config
Config changes require a gateway restart. If the Gateway is running with config watch + in-process restart enabled (the default openclaw gateway path), that restart is usually performed automatically a moment after the config write lands.
Plugin states: disabled vs missing vs invalid

​
Discovery and precedence
OpenClaw scans for plugins in this order (first match wins):
1
Config paths

plugins.load.paths — explicit file or directory paths.
2
Workspace extensions

\<workspace\>/.openclaw/<plugin-root>/*.ts and \<workspace\>/.openclaw/<plugin-root>/*/index.ts.
3
Global extensions

~/.openclaw/<plugin-root>/*.ts and ~/.openclaw/<plugin-root>/*/index.ts.
4
Bundled plugins

Shipped with OpenClaw. Many are enabled by default (model providers, speech). Others require explicit enablement.
​
Enablement rules
plugins.enabled: false disables all plugins
plugins.deny always wins over allow
plugins.entries.\<id\>.enabled: false disables that plugin
Workspace-origin plugins are disabled by default (must be explicitly enabled)
Bundled plugins follow the built-in default-on set unless overridden
Exclusive slots can force-enable the selected plugin for that slot
​
Plugin slots (exclusive categories)
Some categories are exclusive (only one active at a time):
{
  plugins: {
    slots: {
      memory: "memory-core", // or "none" to disable
      contextEngine: "legacy", // or a plugin id
    },
  },
}
Slot	What it controls	Default
memory	Active memory plugin	memory-core
contextEngine	Active context engine	legacy (built-in)
​
CLI reference
openclaw plugins list                    # compact inventory
openclaw plugins inspect <id>            # deep detail
openclaw plugins inspect <id> --json     # machine-readable
openclaw plugins status                  # operational summary
openclaw plugins doctor                  # diagnostics

openclaw plugins install <package>        # install (ClawHub first, then npm)
openclaw plugins install clawhub:<pkg>   # install from ClawHub only
openclaw plugins install <path>          # install from local path
openclaw plugins install -l <path>       # link (no copy) for dev
openclaw plugins update <id>             # update one plugin
openclaw plugins update --all            # update all

openclaw plugins enable <id>
openclaw plugins disable <id>
See openclaw plugins CLI reference for full details.
​
Plugin API overview
Plugins export either a function or an object with register(api):
export default definePluginEntry({
  id: "my-plugin",
  name: "My Plugin",
  register(api) {
    api.registerProvider({
      /* ... */
    });
    api.registerTool({
      /* ... */
    });
    api.registerChannel({
      /* ... */
    });
  },
});
Common registration methods:
Method	What it registers
registerProvider	Model provider (LLM)
registerChannel	Chat channel
registerTool	Agent tool
registerHook / on(...)	Lifecycle hooks
registerSpeechProvider	Text-to-speech / STT
registerMediaUnderstandingProvider	Image/audio analysis
registerImageGenerationProvider	Image generation
registerWebSearchProvider	Web search
registerHttpRoute	HTTP endpoint
registerCommand / registerCli	CLI commands
registerContextEngine	Context engine
registerService	Background service
Hook guard behavior for typed lifecycle hooks:
before_tool_call: { block: true } is terminal; lower-priority handlers are skipped.
before_tool_call: { block: false } is a no-op and does not clear an earlier block.
message_sending: { cancel: true } is terminal; lower-priority handlers are skipped.
message_sending: { cancel: false } is a no-op and does not clear an earlier cancel.
For full typed hook behavior, see SDK Overview.
​
Related
Building Plugins — create your own plugin
Plugin Bundles — Codex/Claude/Cursor bundle compatibility
Plugin Manifest — manifest schema
Registering Tools — add agent tools in a plugin
Plugin Internals — capability model and load pipeline
Community Plugins — third-party listings