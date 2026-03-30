Hooks
Hooks provide an extensible event-driven system for automating actions in response to agent commands and events. Hooks are automatically discovered from directories and can be inspected with openclaw hooks, while hook-pack installation and updates now go through openclaw plugins.
​
Getting Oriented
Hooks are small scripts that run when something happens. There are two kinds:
Hooks (this page): run inside the Gateway when agent events fire, like /new, /reset, /stop, or lifecycle events.
Webhooks: external HTTP webhooks that let other systems trigger work in OpenClaw. See Webhook Hooks or use openclaw webhooks for Gmail helper commands.
Hooks can also be bundled inside plugins; see Plugin hooks. openclaw hooks list shows both standalone hooks and plugin-managed hooks.
Common uses:
Save a memory snapshot when you reset a session
Keep an audit trail of commands for troubleshooting or compliance
Trigger follow-up automation when a session starts or ends
Write files into the agent workspace or call external APIs when events fire
If you can write a small TypeScript function, you can write a hook. Managed and bundled hooks are trusted local code. Workspace hooks are discovered automatically, but OpenClaw keeps them disabled until you explicitly enable them via the CLI or config.
​
Overview
The hooks system allows you to:
Save session context to memory when /new is issued
Log all commands for auditing
Trigger custom automations on agent lifecycle events
Extend OpenClaw’s behavior without modifying core code
​
Getting Started
​
Bundled Hooks
OpenClaw ships with four bundled hooks that are automatically discovered:
💾 session-memory: Saves session context to your agent workspace (default ~/.openclaw/workspace/memory/) when you issue /new or /reset
📎 bootstrap-extra-files: Injects additional workspace bootstrap files from configured glob/path patterns during agent:bootstrap
📝 command-logger: Logs all command events to ~/.openclaw/logs/commands.log
🚀 boot-md: Runs BOOT.md when the gateway starts (requires internal hooks enabled)
List available hooks:
openclaw hooks list
Enable a hook:
openclaw hooks enable session-memory
Check hook status:
openclaw hooks check
Get detailed information:
openclaw hooks info session-memory
​
Onboarding
During onboarding (openclaw onboard), you’ll be prompted to enable recommended hooks. The wizard automatically discovers eligible hooks and presents them for selection.
​
Trust Boundary
Hooks run inside the Gateway process. Treat bundled hooks, managed hooks, and hooks.internal.load.extraDirs as trusted local code. Workspace hooks under <workspace>/hooks/ are repo-local code, so OpenClaw requires an explicit enable step before loading them.
​
Hook Discovery
Hooks are automatically discovered from these directories, in order of increasing override precedence:
Bundled hooks: shipped with OpenClaw; located at <openclaw>/dist/hooks/bundled/ for npm installs (or a sibling hooks/bundled/ for compiled binaries)
Plugin hooks: hooks bundled inside installed plugins (see Plugin hooks)
Managed hooks: ~/.openclaw/hooks/ (user-installed, shared across workspaces; can override bundled and plugin hooks). Extra hook directories configured via hooks.internal.load.extraDirs are also treated as managed hooks and share the same override precedence.
Workspace hooks: <workspace>/hooks/ (per-agent, disabled by default until explicitly enabled; cannot override hooks from other sources)
Workspace hooks can add new hook names for a repo, but they cannot override bundled, managed, or plugin-provided hooks with the same name.
Managed hook directories can be either a single hook or a hook pack (package directory).
Each hook is a directory containing:
my-hook/
├── HOOK.md          # Metadata + documentation
└── handler.ts       # Handler implementation
​
Hook Packs (npm/archives)
Hook packs are standard npm packages that export one or more hooks via openclaw.hooks in package.json. Install them with:
openclaw plugins install <path-or-spec>
Npm specs are registry-only (package name + optional exact version or dist-tag). Git/URL/file specs and semver ranges are rejected.
Bare specs and @latest stay on the stable track. If npm resolves either of those to a prerelease, OpenClaw stops and asks you to opt in explicitly with a prerelease tag such as @beta/@rc or an exact prerelease version.
Example package.json:
{
  "name": "@acme/my-hooks",
  "version": "0.1.0",
  "openclaw": {
    "hooks": ["./hooks/my-hook", "./hooks/other-hook"]
  }
}
Each entry points to a hook directory containing HOOK.md and handler.ts (or index.ts). Hook packs can ship dependencies; they will be installed under ~/.openclaw/hooks/<id>. Each openclaw.hooks entry must stay inside the package directory after symlink resolution; entries that escape are rejected.
Security note: openclaw plugins install installs hook-pack dependencies with npm install --ignore-scripts (no lifecycle scripts). Keep hook pack dependency trees “pure JS/TS” and avoid packages that rely on postinstall builds.
​
Hook Structure
​
HOOK.md Format
The HOOK.md file contains metadata in YAML frontmatter plus Markdown documentation:
---
name: my-hook
description: "Short description of what this hook does"
homepage: https://docs.openclaw.ai/automation/hooks#my-hook
metadata:
  { "openclaw": { "emoji": "🔗", "events": ["command:new"], "requires": { "bins": ["node"] } } }
---

# My Hook

Detailed documentation goes here...

## What It Does

- Listens for `/new` commands
- Performs some action
- Logs the result

## Requirements

- Node.js must be installed

## Configuration

No configuration needed.
​
Metadata Fields
The metadata.openclaw object supports:
emoji: Display emoji for CLI (e.g., "💾")
events: Array of events to listen for (e.g., ["command:new", "command:reset"])
export: Named export to use (defaults to "default")
homepage: Documentation URL
os: Required platforms (e.g., ["darwin", "linux"])
requires: Optional requirements
bins: Required binaries on PATH (e.g., ["git", "node"])
anyBins: At least one of these binaries must be present
env: Required environment variables
config: Required config paths (e.g., ["workspace.dir"])
always: Bypass eligibility checks (boolean)
install: Installation methods (for bundled hooks: [{"id":"bundled","kind":"bundled"}])
​
Handler Implementation
The handler.ts file exports a HookHandler function:
const myHandler = async (event) => {
  // Only trigger on 'new' command
  if (event.type !== "command" || event.action !== "new") {
    return;
  }

  console.log(`[my-hook] New command triggered`);
  console.log(`  Session: ${event.sessionKey}`);
  console.log(`  Timestamp: ${event.timestamp.toISOString()}`);

  // Your custom logic here

  // Optionally send message to user
  event.messages.push("✨ My hook executed!");
};

export default myHandler;
​
Event Context
Each event includes:
{
  type: 'command' | 'session' | 'agent' | 'gateway' | 'message',
  action: string,              // e.g., 'new', 'reset', 'stop', 'received', 'sent'
  sessionKey: string,          // Session identifier
  timestamp: Date,             // When the event occurred
  messages: string[],          // Push messages here to send to user
  context: {
    // Command events (command:new, command:reset):
    sessionEntry?: SessionEntry,       // current session entry
    previousSessionEntry?: SessionEntry, // pre-reset entry (preferred for session-memory)
    commandSource?: string,            // e.g., 'whatsapp', 'telegram'
    senderId?: string,
    workspaceDir?: string,
    cfg?: OpenClawConfig,
    // Command events (command:stop only):
    sessionId?: string,
    // Agent bootstrap events (agent:bootstrap):
    bootstrapFiles?: WorkspaceBootstrapFile[],
    // Message events (see Message Events section for full details):
    from?: string,             // message:received
    to?: string,               // message:sent
    content?: string,
    channelId?: string,
    success?: boolean,         // message:sent
  }
}
​
Event Types
​
Command Events
Triggered when agent commands are issued:
command: All command events (general listener)
command:new: When /new command is issued
command:reset: When /reset command is issued
command:stop: When /stop command is issued
​
Session Events
session:compact:before: Right before compaction summarizes history
session:compact:after: After compaction completes with summary metadata
Internal hook payloads emit these as type: "session" with action: "compact:before" / action: "compact:after"; listeners subscribe with the combined keys above. Specific handler registration uses the literal key format ${type}:${action}. For these events, register session:compact:before and session:compact:after.
​
Agent Events
agent:bootstrap: Before workspace bootstrap files are injected (hooks may mutate context.bootstrapFiles)
​
Gateway Events
Triggered when the gateway starts:
gateway:startup: After channels start and hooks are loaded
​
Session Patch Events
Triggered when session properties are modified:
session:patch: When a session is updated
​
Session Event Context
Session events include rich context about the session and changes:
{
  sessionEntry: SessionEntry, // The complete updated session entry
  patch: {                    // The patch object (only changed fields)
    // Session identity & labeling
    label?: string | null,           // Human-readable session label

    // AI model configuration
    model?: string | null,           // Model override (e.g., "claude-opus-4-5")
    thinkingLevel?: string | null,   // Thinking level ("off"|"low"|"med"|"high")
    verboseLevel?: string | null,    // Verbose output level
    reasoningLevel?: string | null,  // Reasoning mode override
    elevatedLevel?: string | null,   // Elevated mode override
    responseUsage?: "off" | "tokens" | "full" | null, // Usage display mode

    // Tool execution settings
    execHost?: string | null,        // Exec host (sandbox|gateway|node)
    execSecurity?: string | null,    // Security mode (deny|allowlist|full)
    execAsk?: string | null,         // Approval mode (off|on-miss|always)
    execNode?: string | null,        // Node ID for host=node

    // Subagent coordination
    spawnedBy?: string | null,       // Parent session key (for subagents)
    spawnDepth?: number | null,      // Nesting depth (0 = root)

    // Communication policies
    sendPolicy?: "allow" | "deny" | null,          // Message send policy
    groupActivation?: "mention" | "always" | null, // Group chat activation
  },
  cfg: OpenClawConfig            // Current gateway config
}
Security note: Only privileged clients (including the Control UI) can trigger session:patch events. Standard WebChat clients are blocked from patching sessions (see PR #20800), so the hook will not fire from those connections.
See SessionsPatchParamsSchema in src/gateway/protocol/schema/sessions.ts for the complete type definition.
​
Example: Session Patch Logger Hook
const handler = async (event) => {
  if (event.type !== "session" || event.action !== "patch") {
    return;
  }
  const { patch } = event.context;
  console.log(`[session-patch] Session updated: ${event.sessionKey}`);
  console.log(`[session-patch] Changes:`, patch);
};

export default handler;
​
Message Events
Triggered when messages are received or sent:
message: All message events (general listener)
message:received: When an inbound message is received from any channel. Fires early in processing before media understanding. Content may contain raw placeholders like <media:audio> for media attachments that haven’t been processed yet.
message:transcribed: When a message has been fully processed, including audio transcription and link understanding. At this point, transcript contains the full transcript text for audio messages. Use this hook when you need access to transcribed audio content.
message:preprocessed: Fires for every message after all media + link understanding completes, giving hooks access to the fully enriched body (transcripts, image descriptions, link summaries) before the agent sees it.
message:sent: When an outbound message is successfully sent
​
Message Event Context
Message events include rich context about the message:
// message:received context
{
  from: string,           // Sender identifier (phone number, user ID, etc.)
  content: string,        // Message content
  timestamp?: number,     // Unix timestamp when received
  channelId: string,      // Channel (e.g., "whatsapp", "telegram", "discord")
  accountId?: string,     // Provider account ID for multi-account setups
  conversationId?: string, // Chat/conversation ID
  messageId?: string,     // Message ID from the provider
  metadata?: {            // Additional provider-specific data
    to?: string,
    provider?: string,
    surface?: string,
    threadId?: string | number,
    senderId?: string,
    senderName?: string,
    senderUsername?: string,
    senderE164?: string,
    guildId?: string,     // Discord guild / server ID
    channelName?: string, // Channel name (e.g., Discord channel name)
  }
}

// message:sent context
{
  to: string,             // Recipient identifier
  content: string,        // Message content that was sent
  success: boolean,       // Whether the send succeeded
  error?: string,         // Error message if sending failed
  channelId: string,      // Channel (e.g., "whatsapp", "telegram", "discord")
  accountId?: string,     // Provider account ID
  conversationId?: string, // Chat/conversation ID
  messageId?: string,     // Message ID returned by the provider
  isGroup?: boolean,      // Whether this outbound message belongs to a group/channel context
  groupId?: string,       // Group/channel identifier for correlation with message:received
}

// message:transcribed context
{
  from?: string,          // Sender identifier
  to?: string,            // Recipient identifier
  body?: string,          // Raw inbound body before enrichment
  bodyForAgent?: string,  // Enriched body visible to the agent
  transcript: string,     // Audio transcript text
  timestamp?: number,     // Unix timestamp when received
  channelId: string,      // Channel (e.g., "telegram", "whatsapp")
  conversationId?: string,
  messageId?: string,
  senderId?: string,      // Sender user ID
  senderName?: string,    // Sender display name
  senderUsername?: string,
  provider?: string,      // Provider name
  surface?: string,       // Surface name
  mediaPath?: string,     // Path to the media file that was transcribed
  mediaType?: string,     // MIME type of the media
}

// message:preprocessed context
{
  from?: string,          // Sender identifier
  to?: string,            // Recipient identifier
  body?: string,          // Raw inbound body
  bodyForAgent?: string,  // Final enriched body after media/link understanding
  transcript?: string,    // Transcript when audio was present
  timestamp?: number,     // Unix timestamp when received
  channelId: string,      // Channel (e.g., "telegram", "whatsapp")
  conversationId?: string,
  messageId?: string,
  senderId?: string,      // Sender user ID
  senderName?: string,    // Sender display name
  senderUsername?: string,
  provider?: string,      // Provider name
  surface?: string,       // Surface name
  mediaPath?: string,     // Path to the media file
  mediaType?: string,     // MIME type of the media
  isGroup?: boolean,
  groupId?: string,
}
​
Example: Message Logger Hook
const isMessageReceivedEvent = (event: { type: string; action: string }) =>
  event.type === "message" && event.action === "received";
const isMessageSentEvent = (event: { type: string; action: string }) =>
  event.type === "message" && event.action === "sent";

const handler = async (event) => {
  if (isMessageReceivedEvent(event as { type: string; action: string })) {
    console.log(`[message-logger] Received from ${event.context.from}: ${event.context.content}`);
  } else if (isMessageSentEvent(event as { type: string; action: string })) {
    console.log(`[message-logger] Sent to ${event.context.to}: ${event.context.content}`);
  }
};

export default handler;
​
Tool Result Hooks (Plugin API)
These hooks are not event-stream listeners; they let plugins synchronously adjust tool results before OpenClaw persists them.
tool_result_persist: transform tool results before they are written to the session transcript. Must be synchronous; return the updated tool result payload or undefined to keep it as-is. See Agent Loop.
​
Plugin Hook Events
​
before_tool_call
Runs before each tool call. Plugins can modify parameters, block the call, or request user approval.
Return fields:
params: Override tool parameters (merged with original params)
block: Set to true to block the tool call
blockReason: Reason shown to the agent when blocked
requireApproval: Pause execution and wait for user approval via channels
The requireApproval field triggers native platform approval (Telegram buttons, Discord components, /approve command) instead of relying on the agent to cooperate:
{
  requireApproval: {
    title: "Sensitive operation",
    description: "This tool call modifies production data",
    severity: "warning",       // "info" | "warning" | "critical"
    timeoutMs: 120000,         // default: 120s
    timeoutBehavior: "deny",   // "allow" | "deny" (default)
    onResolution: async (decision) => {
      // Called after the user resolves: "allow-once", "allow-always", "deny", "timeout", or "cancelled"
    },
  }
}
The onResolution callback is invoked with the final decision string after the approval resolves, times out, or is cancelled. It runs in-process within the plugin (not sent to the gateway). Use it to persist decisions, update caches, or perform cleanup.
The pluginId field is stamped automatically by the hook runner from the plugin registration. When multiple plugins return requireApproval, the first one (highest priority) wins.
block takes precedence over requireApproval: if the merged hook result has both block: true and a requireApproval field, the tool call is blocked immediately without triggering the approval flow. This ensures a higher-priority plugin’s block cannot be overridden by a lower-priority plugin’s approval request.
If the gateway is unavailable or does not support plugin approvals, the tool call falls back to a soft block using the description as the block reason.
​
Compaction lifecycle
Compaction lifecycle hooks exposed through the plugin hook runner:
before_compaction: Runs before compaction with count/token metadata
after_compaction: Runs after compaction with compaction summary metadata
​
Future Events
Planned event types:
session:start: When a new session begins
session:end: When a session ends
agent:error: When an agent encounters an error
​
Creating Custom Hooks
​
1. Choose Location
Workspace hooks (<workspace>/hooks/): Per-agent; can add new hook names but cannot override bundled, managed, or plugin hooks with the same name
Managed hooks (~/.openclaw/hooks/): Shared across workspaces; can override bundled and plugin hooks
​
2. Create Directory Structure
mkdir -p ~/.openclaw/hooks/my-hook
cd ~/.openclaw/hooks/my-hook
​
3. Create HOOK.md
---
name: my-hook
description: "Does something useful"
metadata: { "openclaw": { "emoji": "🎯", "events": ["command:new"] } }
---

# My Custom Hook

This hook does something useful when you issue `/new`.
​
4. Create handler.ts
const handler = async (event) => {
  if (event.type !== "command" || event.action !== "new") {
    return;
  }

  console.log("[my-hook] Running!");
  // Your logic here
};

export default handler;
​
5. Enable and Test
# Verify hook is discovered
openclaw hooks list

# Enable it
openclaw hooks enable my-hook

# Restart your gateway process (menu bar app restart on macOS, or restart your dev process)

# Trigger the event
# Send /new via your messaging channel
​
Configuration
​
New Config Format (Recommended)
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "session-memory": { "enabled": true },
        "command-logger": { "enabled": false }
      }
    }
  }
}
​
Per-Hook Configuration
Hooks can have custom configuration:
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "my-hook": {
          "enabled": true,
          "env": {
            "MY_CUSTOM_VAR": "value"
          }
        }
      }
    }
  }
}
​
Extra Directories
Load hooks from additional directories (treated as managed hooks, same override precedence):
{
  "hooks": {
    "internal": {
      "enabled": true,
      "load": {
        "extraDirs": ["/path/to/more/hooks"]
      }
    }
  }
}
​
Legacy Config Format (Still Supported)
The old config format still works for backwards compatibility:
{
  "hooks": {
    "internal": {
      "enabled": true,
      "handlers": [
        {
          "event": "command:new",
          "module": "./hooks/handlers/my-handler.ts",
          "export": "default"
        }
      ]
    }
  }
}
Note: module must be a workspace-relative path. Absolute paths and traversal outside the workspace are rejected.
Migration: Use the new discovery-based system for new hooks. Legacy handlers are loaded after directory-based hooks.
​
CLI Commands
​
List Hooks
# List all hooks
openclaw hooks list

# Show only eligible hooks
openclaw hooks list --eligible

# Verbose output (show missing requirements)
openclaw hooks list --verbose

# JSON output
openclaw hooks list --json
​
Hook Information
# Show detailed info about a hook
openclaw hooks info session-memory

# JSON output
openclaw hooks info session-memory --json
​
Check Eligibility
# Show eligibility summary
openclaw hooks check

# JSON output
openclaw hooks check --json
​
Enable/Disable
# Enable a hook
openclaw hooks enable session-memory

# Disable a hook
openclaw hooks disable command-logger
​
Bundled hook reference
​
session-memory
Saves session context to memory when you issue /new or /reset.
Events: command:new, command:reset
Requirements: workspace.dir must be configured
Output: <workspace>/memory/YYYY-MM-DD-slug.md (defaults to ~/.openclaw/workspace)
What it does:
Uses the pre-reset session entry to locate the correct transcript
Extracts the last 15 user/assistant messages from the conversation (configurable)
Uses LLM to generate a descriptive filename slug
Saves session metadata to a dated memory file
Example output:
# Session: 2026-01-16 14:30:00 UTC

- **Session Key**: agent:main:main
- **Session ID**: abc123def456
- **Source**: telegram

## Conversation Summary

user: Can you help me design the API?
assistant: Sure! Let's start with the endpoints...
Filename examples:
2026-01-16-vendor-pitch.md
2026-01-16-api-design.md
2026-01-16-1430.md (fallback timestamp if slug generation fails)
Enable:
openclaw hooks enable session-memory
​
bootstrap-extra-files
Injects additional bootstrap files (for example monorepo-local AGENTS.md / TOOLS.md) during agent:bootstrap.
Events: agent:bootstrap
Requirements: workspace.dir must be configured
Output: No files written; bootstrap context is modified in-memory only.
Config:
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "bootstrap-extra-files": {
          "enabled": true,
          "paths": ["packages/*/AGENTS.md", "packages/*/TOOLS.md"]
        }
      }
    }
  }
}
Config options:
paths (string[]): glob/path patterns to resolve from the workspace.
patterns (string[]): alias of paths.
files (string[]): alias of paths.
Notes:
Paths are resolved relative to workspace.
Files must stay inside workspace (realpath-checked).
Only recognized bootstrap basenames are loaded (AGENTS.md, SOUL.md, TOOLS.md, IDENTITY.md, USER.md, HEARTBEAT.md, BOOTSTRAP.md, MEMORY.md, memory.md).
For subagent/cron sessions a narrower allowlist applies (AGENTS.md, TOOLS.md, SOUL.md, IDENTITY.md, USER.md).
Enable:
openclaw hooks enable bootstrap-extra-files
​
command-logger
Logs all command events to a centralized audit file.
Events: command
Requirements: None
Output: ~/.openclaw/logs/commands.log
What it does:
Captures event details (command action, timestamp, session key, sender ID, source)
Appends to log file in JSONL format
Runs silently in the background
Example log entries:
{"timestamp":"2026-01-16T14:30:00.000Z","action":"new","sessionKey":"agent:main:main","senderId":"+1234567890","source":"telegram"}
{"timestamp":"2026-01-16T15:45:22.000Z","action":"stop","sessionKey":"agent:main:main","senderId":"user@example.com","source":"whatsapp"}
View logs:
# View recent commands
tail -n 20 ~/.openclaw/logs/commands.log

# Pretty-print with jq
cat ~/.openclaw/logs/commands.log | jq .

# Filter by action
grep '"action":"new"' ~/.openclaw/logs/commands.log | jq .
Enable:
openclaw hooks enable command-logger
​
boot-md
Runs BOOT.md when the gateway starts (after channels start). Internal hooks must be enabled for this to run.
Events: gateway:startup
Requirements: workspace.dir must be configured
What it does:
Reads BOOT.md from your workspace
Runs the instructions via the agent runner
Sends any requested outbound messages via the message tool
Enable:
openclaw hooks enable boot-md
​
Best Practices
​
Keep Handlers Fast
Hooks run during command processing. Keep them lightweight:
// ✓ Good - async work, returns immediately
const handler: HookHandler = async (event) => {
  void processInBackground(event); // Fire and forget
};

// ✗ Bad - blocks command processing
const handler: HookHandler = async (event) => {
  await slowDatabaseQuery(event);
  await evenSlowerAPICall(event);
};
​
Handle Errors Gracefully
Always wrap risky operations:
const handler: HookHandler = async (event) => {
  try {
    await riskyOperation(event);
  } catch (err) {
    console.error("[my-handler] Failed:", err instanceof Error ? err.message : String(err));
    // Don't throw - let other handlers run
  }
};
​
Filter Events Early
Return early if the event isn’t relevant:
const handler: HookHandler = async (event) => {
  // Only handle 'new' commands
  if (event.type !== "command" || event.action !== "new") {
    return;
  }

  // Your logic here
};
​
Use Specific Event Keys
Specify exact events in metadata when possible:
metadata: { "openclaw": { "events": ["command:new"] } } # Specific
Rather than:
metadata: { "openclaw": { "events": ["command"] } } # General - more overhead
​
Debugging
​
Enable Hook Logging
The gateway logs hook loading at startup:
Registered hook: session-memory -> command:new
Registered hook: bootstrap-extra-files -> agent:bootstrap
Registered hook: command-logger -> command
Registered hook: boot-md -> gateway:startup
​
Check Discovery
List all discovered hooks:
openclaw hooks list --verbose
​
Check Registration
In your handler, log when it’s called:
const handler: HookHandler = async (event) => {
  console.log("[my-handler] Triggered:", event.type, event.action);
  // Your logic
};
​
Verify Eligibility
Check why a hook isn’t eligible:
openclaw hooks info my-hook
Look for missing requirements in the output.
​
Testing
​
Gateway Logs
Monitor gateway logs to see hook execution:
# macOS
./scripts/clawlog.sh -f

# Other platforms
tail -f ~/.openclaw/gateway.log
​
Test Hooks Directly
Test your handlers in isolation:
import { test } from "vitest";
import myHandler from "./hooks/my-hook/handler.js";

test("my handler works", async () => {
  const event = {
    type: "command",
    action: "new",
    sessionKey: "test-session",
    timestamp: new Date(),
    messages: [],
    context: { foo: "bar" },
  };

  await myHandler(event);

  // Assert side effects
});
​
Architecture
​
Core Components
src/hooks/types.ts: Type definitions
src/hooks/workspace.ts: Directory scanning and loading
src/hooks/frontmatter.ts: HOOK.md metadata parsing
src/hooks/config.ts: Eligibility checking
src/hooks/hooks-status.ts: Status reporting
src/hooks/loader.ts: Dynamic module loader
src/cli/hooks-cli.ts: CLI commands
src/gateway/server-startup.ts: Loads hooks at gateway start
src/auto-reply/reply/commands-core.ts: Triggers command events
​
Discovery Flow
Gateway startup
    ↓
Scan directories (bundled → plugin → managed + extra dirs → workspace)
    ↓
Parse HOOK.md files
    ↓
Sort by override precedence (bundled < plugin < managed < workspace)
    ↓
Check eligibility (bins, env, config, os)
    ↓
Load handlers from eligible hooks
    ↓
Register handlers for events
​
Event Flow
User sends /new
    ↓
Command validation
    ↓
Create hook event
    ↓
Trigger hook (all registered handlers)
    ↓
Command processing continues
    ↓
Session reset
​
Troubleshooting
​
Hook Not Discovered
Check directory structure:
ls -la ~/.openclaw/hooks/my-hook/
# Should show: HOOK.md, handler.ts
Verify HOOK.md format:
cat ~/.openclaw/hooks/my-hook/HOOK.md
# Should have YAML frontmatter with name and metadata
List all discovered hooks:
openclaw hooks list
​
Hook Not Eligible
Check requirements:
openclaw hooks info my-hook
Look for missing:
Binaries (check PATH)
Environment variables
Config values
OS compatibility
​
Hook Not Executing
Verify hook is enabled:
openclaw hooks list
# Should show ✓ next to enabled hooks
Restart your gateway process so hooks reload.
Check gateway logs for errors:
./scripts/clawlog.sh | grep hook
​
Handler Errors
Check for TypeScript/import errors:
# Test import directly
node -e "import('./path/to/handler.ts').then(console.log)"
​
Migration Guide
​
From Legacy Config to Discovery
Before:
{
  "hooks": {
    "internal": {
      "enabled": true,
      "handlers": [
        {
          "event": "command:new",
          "module": "./hooks/handlers/my-handler.ts"
        }
      ]
    }
  }
}
After:
Create hook directory:
mkdir -p ~/.openclaw/hooks/my-hook
mv ./hooks/handlers/my-handler.ts ~/.openclaw/hooks/my-hook/handler.ts
Create HOOK.md:
---
name: my-hook
description: "My custom hook"
metadata: { "openclaw": { "emoji": "🎯", "events": ["command:new"] } }
---

# My Hook

Does something useful.
Update config:
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "my-hook": { "enabled": true }
      }
    }
  }
}
Verify and restart your gateway process:
openclaw hooks list
# Should show: 🎯 my-hook ✓
Benefits of migration:
Automatic discovery
CLI management
Eligibility checking
Better documentation
Consistent structure


Bundled Hooks
This directory contains hooks that ship with OpenClaw. These hooks are automatically discovered and can be enabled/disabled via CLI or configuration.

Available Hooks
💾 session-memory
Automatically saves session context to memory when you issue /new or /reset.

Events: command:new, command:reset What it does: Creates a dated memory file with LLM-generated slug based on conversation content. Output: <workspace>/memory/YYYY-MM-DD-slug.md (defaults to ~/.openclaw/workspace)

Enable:

openclaw hooks enable session-memory
📎 bootstrap-extra-files
Injects extra bootstrap files (for example monorepo AGENTS.md/TOOLS.md) during prompt assembly.

Events: agent:bootstrap What it does: Expands configured workspace glob/path patterns and appends matching bootstrap files to injected context. Output: No files written; context is modified in-memory only.

Enable:

openclaw hooks enable bootstrap-extra-files
📝 command-logger
Logs all command events to a centralized audit file.

Events: command (all commands) What it does: Appends JSONL entries to command log file. Output: ~/.openclaw/logs/commands.log

Enable:

openclaw hooks enable command-logger
🚀 boot-md
Runs BOOT.md whenever the gateway starts (after channels start).

Events: gateway:startup What it does: Executes BOOT.md instructions via the agent runner. Output: Whatever the instructions request (for example, outbound messages).

Enable:

openclaw hooks enable boot-md
Hook Structure
Each hook is a directory containing:

HOOK.md: Metadata and documentation in YAML frontmatter + Markdown
handler.ts: The hook handler function (default export)
Example structure:

session-memory/
├── HOOK.md          # Metadata + docs
└── handler.ts       # Handler implementation
HOOK.md Format
---
name: my-hook
description: "Short description"
homepage: https://docs.openclaw.ai/automation/hooks#my-hook
metadata:
  { "openclaw": { "emoji": "🔗", "events": ["command:new"], "requires": { "bins": ["node"] } } }
---
# Hook Title

Documentation goes here...
Metadata Fields
emoji: Display emoji for CLI
events: Array of events to listen for (e.g., ["command:new", "session:start"])
requires: Optional requirements
bins: Required binaries on PATH
anyBins: At least one of these binaries must be present
env: Required environment variables
config: Required config paths (e.g., ["workspace.dir"])
os: Required platforms (e.g., ["darwin", "linux"])
install: Installation methods (for bundled hooks: [{"id":"bundled","kind":"bundled"}])
Creating Custom Hooks
To create your own hooks, place them in:

Workspace hooks: <workspace>/hooks/ (highest precedence)
Managed hooks: ~/.openclaw/hooks/ (shared across workspaces)
Custom hooks follow the same structure as bundled hooks.

Managing Hooks
List all hooks:

openclaw hooks list
Show hook details:

openclaw hooks info session-memory
Check hook status:

openclaw hooks check
Enable/disable:

openclaw hooks enable session-memory
openclaw hooks disable command-logger
Configuration
Hooks can be configured in ~/.openclaw/openclaw.json:

{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "session-memory": {
          "enabled": true
        },
        "command-logger": {
          "enabled": false
        }
      }
    }
  }
}
Event Types
Currently supported events:

command: All command events
command:new: /new command specifically
command:reset: /reset command
command:stop: /stop command
agent:bootstrap: Before workspace bootstrap files are injected
gateway:startup: Gateway startup (after channels start)
More event types coming soon (session lifecycle, agent errors, etc.).

Handler API
Hook handlers receive an InternalHookEvent object:

interface InternalHookEvent {
  type: "command" | "session" | "agent" | "gateway";
  action: string; // e.g., 'new', 'reset', 'stop'
  sessionKey: string;
  context: Record<string, unknown>;
  timestamp: Date;
  messages: string[]; // Push messages here to send to user
}
Example handler:

import type { HookHandler } from "../../src/hooks/hooks.js";

const myHandler: HookHandler = async (event) => {
  if (event.type !== "command" || event.action !== "new") {
    return;
  }

  // Your logic here
  console.log("New command triggered!");

  // Optionally send message to user
  event.messages.push("✨ Hook executed!");
};

export default myHandler;