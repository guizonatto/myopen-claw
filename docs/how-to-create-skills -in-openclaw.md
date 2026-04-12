keep this doc update once in a week: 
sources:
https://docs.openclaw.ai/tools/skills
https://docs.openclaw.ai/tools/skills-config
https://docs.openclaw.ai/tools/creating-skills
last update: 23/02/2026

# 🛠️ How to Create Skills in OpenClaw

> **Nota:** MCP significa sempre Model Context Protocol. Skills textuais (YAML/JSON/MD) descrevem operações a serem executadas por um MCP, referenciado no campo `mcp:`.

Veja também: [INDEX.md](INDEX.md)


## 1. Create the Skill Directory

Skills live in your workspace. Create a new folder:

```sh
mkdir -p ~/.openclaw/workspace/skills/hello-world
```
my-skill/
  SKILL.md          # Required — main instructions
  README.md         # Optional — documentation
  scripts/          # Optional — helper scripts
    fetch-data.sh
  references/       # Optional — context files
    api-docs.md
  examples/         # Optional — usage examples
    sample-output.md

## 2. Write a Textual Skill (YAML/JSON/MD)

Create a YAML/JSON/MD file describing the operation and referencing the MCP executor:

```yaml
operation: fetch_trending_topics
mcp: trends_mcp
params:
  region: "BR"
  limit: 10
```

Or, for legacy Python skills, see below.


## 3. Add Tools (Optional)

You can define custom tool schemas in the frontmatter or instruct the agent to use existing system tools (like `exec` or `browser`).
Skills can also ship inside plugins alongside the tools they document.


## 4. Load the Skill

Start a new session so OpenClaw picks up the skill:

```sh
# From chat
/new

# Or restart the gateway
openclaw gateway restart
```

Verify the skill loaded:

```sh
openclaw skills list
```


## 5. Test the Skill

Send a message that should trigger the skill:

```sh
openclaw agent --message "give me a greeting"
```
Or just chat with the agent and ask for a greeting.

---


<details>
<summary><strong>Skill Metadata Reference</strong></summary>

The YAML frontmatter supports these fields:

| Field                          | Required | Description                                 |
|------------------------------- |----------|---------------------------------------------|
| name                           | Yes      | Unique identifier (snake_case)              |
| description                    | Yes      | One-line description shown to the agent     |
| metadata.openclaw.os           | No       | OS filter (["darwin"], ["linux"], etc.)    |
| metadata.openclaw.requires.bins | No      | Required binaries on PATH                   |
| metadata.openclaw.requires.config | No    | Required config keys                        |

</details>

# Skill Code Sample #
---
name: my-custom-skill
description: Short summary of what this skill does
version: 1.0.0
openclaw:
  emoji: "🔧"
  requires:
    env:
      - MY_API_KEY
    bins:
      - node
      - curl
  primaryEnv: MY_API_KEY
---

# My Custom Skill

## Purpose
This skill does X when the user asks for Y.

## Workflow
1. Parse the user's request for...
2. Call the MCP tool `tool_name` with...
3. Format the response as...

## Rules
- Always confirm before destructive operations
- Never expose API keys in output
- If the MCP server is unreachable, suggest alternatives
---


## Best Practices

> - **Be concise:** Instruct the model on what to do, not how to be an AI.
> - **Safety first:** If your skill uses `exec`, ensure prompts don’t allow arbitrary command injection from untrusted input.
> - **Test locally:** Use `openclaw agent --message "..."` to test before sharing.
> - **Use ClawHub:** Browse and contribute skills at [ClawHub](https://clawhub.com).

---


## Where Skills Live

| Location                  | Precedence | Scope                |
|---------------------------|------------|----------------------|
| `<workspace>/skills/`     | Highest    | Per-agent            |
| `~/.openclaw/skills/`     | Medium     | Shared (all agents)  |
| Bundled (with OpenClaw)   | Lowest     | Global               |
| skills.load.extraDirs     | Lowest     | Custom shared folders |

homepage — optional URL shown as “Website” in the macOS Skills UI.
os — optional list of platforms (darwin, linux, win32). If set, the skill is only eligible on those OSes.
requires.bins — list; each must exist on PATH.
requires.anyBins — list; at least one must exist on PATH.
requires.env — list; env var must exist or be provided in config.
requires.config — list of openclaw.json paths that must be truthy.
primaryEnv — env var name associated with skills.entries.<name>.apiKey.
install — optional array of installer specs used by the macOS Skills UI (brew/node/go/uv/download).
Note on sandboxing:
requires.bins is checked on the host at skill load time.
If an agent is sandboxed, the binary must also exist inside the container. Install it via agents.defaults.sandbox.docker.setupCommand (or a custom image). setupCommand runs once after the container is created. Package installs also require network egress, a writable root FS, and a root user in the sandbox. Example: the summarize skill (skills/summarize/SKILL.md) needs the summarize CLI in the sandbox container to run there.
Installer example:
env: injected only if the variable isn’t already set in the process.
apiKey: convenience for skills that declare metadata.openclaw.primaryEnv. Supports plaintext string or SecretRef object ({ source, provider, id }).
config: optional bag for custom per-skill fields; custom keys must live here.
allowBundled: optional allowlist for bundled skills only. If set, only bundled skills in the list are eligible (managed/workspace skills unaffected).
total = 195 + Σ (97 + len(name_escaped) + len(description_escaped) + len(location_escaped))
env: environment variables injected for the agent run (only if not already set).
apiKey: optional convenience for skills that declare a primary env var. Supports plaintext string or SecretRef object ({ source, provider, id }).

---

## Skills: Advanced Details & Management

<details>
<summary><strong>Locations and Precedence</strong></summary>

OpenClaw loads skills from these sources:

- Extra skill folders: configured with `skills.load.extraDirs`
- Bundled skills: shipped with the install (npm package or OpenClaw.app)
- Managed/local skills: `~/.openclaw/skills`
- Personal agent skills: `~/.agents/skills`
- Project agent skills: `<workspace>/.agents/skills`
- Workspace skills: `<workspace>/skills`

If a skill name conflicts, precedence is:
`<workspace>/skills` (highest) → `<workspace>/.agents/skills` → `~/.agents/skills` → `~/.openclaw/skills` → bundled skills → `skills.load.extraDirs` (lowest)

**Per-agent vs shared skills:**
- Per-agent: `<workspace>/skills` (only for that agent)
- Project agent: `<workspace>/.agents/skills` (applies to workspace)
- Personal agent: `~/.agents/skills` (across workspaces)
- Shared: `~/.openclaw/skills` (all agents on the machine)
- ExtraDirs: for common skill packs

If the same skill name exists in more than one place, the usual precedence applies.
</details>

<details>
<summary><strong>Plugins + Skills</strong></summary>

Plugins can ship their own skills by listing skill directories in `openclaw.plugin.json` (paths relative to the plugin root). Plugin skills load when the plugin is enabled. These are merged into the same low-precedence path as `skills.load.extraDirs`.
</details>

<details>
<summary><strong>ClawHub (Install + Sync)</strong></summary>

ClawHub is the public skills registry for OpenClaw. Browse at [clawhub.com](https://clawhub.com).

**Common flows:**

- Install a skill:
  ```sh
  openclaw skills install <skill-slug>
  ```
- Update all installed skills:
  ```sh
  openclaw skills update --all
  ```
- Sync (scan + publish updates):
  ```sh
  clawhub sync --all
  ```
</details>

<details>
<summary><strong>Security Notes</strong></summary>

> - Treat third-party skills as untrusted code. Read them before enabling.
> - Prefer sandboxed runs for untrusted inputs and risky tools. See Sandboxing.
> - Only accepts skill roots and SKILL.md files whose resolved realpath stays inside the configured root.
> - `skills.entries.*.env` and `skills.entries.*.apiKey` inject secrets into the host process for that agent turn (not the sandbox). Keep secrets out of prompts and logs.
> - For a broader threat model and checklists, see Security.
</details>

<details>
<summary><strong>Skill Format Example</strong></summary>

```yaml
---
name: image-lab
description: Generate or edit images via a provider-backed image workflow
---
```
Notes:
- Follows the AgentSkills spec for layout/intent.
- Parser supports single-line frontmatter keys only.
- `metadata` should be a single-line JSON object.
- Use `{baseDir}` in instructions to reference the skill folder path.
</details>

<details>
<summary><strong>Gating (Load-time Filters)</strong></summary>

OpenClaw filters skills at load time using metadata (single-line JSON):

```yaml
---
name: image-lab
description: Generate or edit images via a provider-backed image workflow
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["uv"], "env": ["GEMINI_API_KEY"], "config": ["browser.enabled"] },
        "primaryEnv": "GEMINI_API_KEY",
      },
  }
---
```
Fields under `metadata.openclaw`:
- `always: true` — always include the skill (skip other gates)
- `emoji` — optional emoji for UI
- `os` — list of platforms (darwin, linux, win32)
- `requires.bins` — binaries required on PATH
- `requires.env` — env var must exist or be provided in config
- `requires.config` — config keys that must be truthy
- `primaryEnv` — env var name associated with `skills.entries.<name>.apiKey`
- `install` — array of installer specs
</details>

<details>
<summary><strong>Config Overrides Example (~/.openclaw/openclaw.json)</strong></summary>

```json5
{
  skills: {
    entries: {
      "image-lab": {
        enabled: true,
        apiKey: { source: "env", provider: "default", id: "GEMINI_API_KEY" },
        env: {
          GEMINI_API_KEY: "GEMINI_KEY_HERE",
        },
        config: {
          endpoint: "https://example.invalid",
          model: "nano-pro",
        },
      },
      peekaboo: { enabled: true },
      sag: { enabled: false },
    },
  },
}
```
Notes:
- If the skill name contains hyphens, quote the key (JSON5 allows quoted keys).
- If you want stock image generation/editing inside OpenClaw itself, use the core `image_generate` tool with `agents.defaults.imageGenerationModel` instead of a bundled skill.
- For native image analysis, use the `image` tool with `agents.defaults.imageModel`.
- For native image generation/editing, use `image_generate` with `agents.defaults.imageGenerationModel`.
- If you pick openai/*, google/*, fal/*, or another provider-specific image model, add that provider’s auth/API key too.
- Config keys match the skill name by default. If a skill defines `metadata.openclaw.skillKey`, use that key under `skills.entries`.
</details>

<details>
<summary><strong>Environment Injection (per agent run)</strong></summary>

When an agent run starts, OpenClaw:
1. Reads skill metadata.
2. Applies any `skills.entries.<key>.env` or `skills.entries.<key>.apiKey` to process.env.
3. Builds the system prompt with eligible skills.
4. Restores the original environment after the run ends.
This is scoped to the agent run, not a global shell environment.
</details>

<details>
<summary><strong>Session Snapshot & Hot Reload</strong></summary>

OpenClaw snapshots the eligible skills when a session starts and reuses that list for subsequent turns in the same session. Changes to skills or config take effect on the next new session. Skills can also refresh mid-session when the skills watcher is enabled or when a new eligible remote node appears.
</details>

<details>
<summary><strong>Token Impact (Skills List)</strong></summary>

When skills are eligible, OpenClaw injects a compact XML list of available skills into the system prompt. The cost is deterministic:

- Base overhead (only when ≥1 skill): 195 characters
- Per skill: 97 characters + the length of the XML-escaped <name>, <description>, and <location> values

Formula:
```
total = 195 + Σ (97 + len(name_escaped) + len(description_escaped) + len(location_escaped))
```
Token counts vary by model tokenizer. A rough OpenAI-style estimate is ~4 chars/token, so 97 chars ≈ 24 tokens per skill plus your actual field lengths.
</details>

<details>
<summary><strong>Sandboxed Skills + Env Vars</strong></summary>

When a session is sandboxed, skill processes run inside Docker. The sandbox does not inherit the host process.env.

Use one of:
- `agents.defaults.sandbox.docker.env` (or per-agent `agents.list[].sandbox.docker.env`)
- Bake the env into your custom sandbox image

Global env and `skills.entries.<skill>.env`/`apiKey` apply to host runs only.
</details>

---

## Looking for More Skills?

Browse [clawhub.com](https://clawhub.com) for more skills.