The Six Changes That Made All the Difference
1. Train Your Agent to Travel Light
The problem: Default session loading is wasteful.

The fix: Tell OpenClaw exactly what to load at startup — and what to skip.

I added this rule to my agent’s system configuration:

SESSION START PROTOCOL:

Load only:
- SOUL.md (core instructions)
- USER.md (my profile)
- IDENTITY.md (agent identity)
- Today's memory file only

Do NOT load:
- Full conversation history
- Old MEMORY.md files
- Previous session outputs

When I ask about the past:
- Search memory on-demand
- Pull specific pieces, not everything

At session end:
- Save today's summary to dated file
- Include: tasks done, decisions made, blockers, next steps
The result: Session startup dropped from 50KB to 6KB. Cost per session went from $0.38 to $0.04.

That one change saved me ~$70/month.

2. Match the Model to the Job
The problem: Using premium compute for basic tasks.

The fix: Make Haiku the default, reserve Sonnet for actual thinking.

OpenClaw lets you configure which model to use. I edited ~/.openclaw/openclaw.json:

{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-haiku-4-5"
      },
      "models": {
        "anthropic/claude-sonnet-4-5": {
          "alias": "sonnet"
        },
        "anthropic/claude-haiku-4-5": {
          "alias": "haiku"
        }
      }
    }
  }
}
Then I gave my agent clear guidance:

MODEL USAGE:

Default to Haiku for:
- File operations
- Simple commands
- Status checks
- Monitoring
- Basic validation

Switch to Sonnet only when:
- Complex problem-solving required
- Architecture decisions needed
- Code review for security
- Strategic planning
- Deep analysis requested

When in doubt, try Haiku first.
The result: About 85% of my tasks now run on Haiku, which costs 12x less than Sonnet. Monthly model costs dropped from $850 to $85.

And honestly? For routine tasks, I can’t tell the difference.

3. Make Health Checks Free
The problem: Paying for thousands of “still alive?” checks.

The fix: Route heartbeats to a free local model using Ollama.

Ollama lets you run open-source language models on your own computer. They’re not as powerful as Claude, but for a simple health check? Perfect.

Setup in 5 minutes:

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Get a small model
ollama pull llama3.2:3b

# Start the service
ollama serve
Then update your OpenClaw config:

{
  "heartbeat": {
    "every": "1h",
    "model": "ollama/llama3.2:3b",
    "session": "main",
    "target": "slack",
    "prompt": "Quick check: any updates needed?"
  }
}
The result: Heartbeat costs went from $52/month to $0. Literally zero.

The agent is just as reliable. The checks still happen. They just happen on my laptop instead of costing money.

4. Install Speed Bumps
The problem: No protection against runaway automation.

The fix: Add rate limits and budget controls.

I put these rules in my system prompt:

RATE LIMITS:

- Minimum 5 seconds between API calls
- Minimum 10 seconds between web searches
- Max 5 searches in a row, then 2-minute cooldown
- Batch similar work (one request, not ten)
- On rate limit error: stop, wait 5 minutes, retry

BUDGET CAPS:
Daily max: $5 (warn at $4)
Monthly max: $180 (warn at $140)
The result: No more surprise bills. The one time my agent tried to spiral into an expensive loop, the rate limits kicked in and stopped it cold.

This didn’t save me recurring costs, but it prevented that $180 weekend disaster from ever happening again.

5. Keep Your Files Lean
The problem: Bloated workspace files waste tokens.

The fix: Minimal, focused context files.

I created ultra-lean templates:

SOUL.md (agent instructions):

# Core Operating Principles

## Model Selection
- Default: Haiku
- Escalate to Sonnet for: complex reasoning, security, architecture

## Rate Limits
- 5s between API calls
- 10s between searches
- Max 5 searches, then break

## Reference
See OPTIMIZATION.md for full guidelines
USER.md (my profile):

# User Context

Name: [Your name]
Timezone: [Your timezone]
Mission: [What you're building]

## Goals
- [Goal 1]
- [Goal 2]
- [Goal 3]
Every line in these files gets sent with every API call. Keep them minimal.

The result: Reduced baseline context by 40%, saving ~$30/month.

6. Leverage Prompt Caching
The problem: Sending the same context repeatedly at full price.

The solution: Claude’s prompt caching gives you a 90% discount on reused content.

Here’s how it works: when you send content to Claude, it gets cached for 5 minutes. If you send it again within that window, you pay 90% less.

Example from my workflow:

I generated 45 personalized emails in one sitting. Each needed the same product context.

Without caching:

45 emails × 4,500 tokens = 202,500 tokens
Cost: ~$608
With caching:

First email: 4,500 tokens at full price = $13.50
Next 44 emails: 198,000 tokens at 90% off = $5.94
Total: $19.44
Savings: $588.56 in one session.

I enabled caching in my config:

{
  "cache": {
    "enabled": true,
    "ttl": "5m",
    "priority": "high"
  },
  "models": {
    "anthropic/claude-sonnet-4-5": {
      "cache": true
    },
    "anthropic/claude-haiku-4-5": {
      "cache": false
    }
  }
}
Key insight: Only cache for Sonnet. Haiku is already so cheap that caching overhead isn’t worth it.

Pro tips:

Batch similar tasks within 5-minute windows
Keep your SOUL.md and USER.md stable (changes invalidate cache)
Separate stable reference docs from dynamic notes
The result: Another $200–300/month saved when doing batch work.

The Numbers Don’t Lie
Here’s my before and after:

Cost Driver Before After Savings Session loading $78/mo $8/mo 90% Model usage $850/mo $85/mo 90% Heartbeat checks $52/mo $0 100% Prompt caching Full price 90% off Variable Rate limit protection Lost $180 once $0 Priceless Total ~$1,200/mo ~$48/mo 96%

And the best part? My agent works exactly the same. Same capabilities, same reliability, same results.

I just stopped paying luxury prices for economy tasks.

How to Do This (Quick Start Guide)
Don’t try to implement everything at once. Here’s the order I recommend:

Week 1: Quick Wins (30 minutes)
Add session initialization rules to system prompt
Switch default model to Haiku in config
Add model selection guidelines to system prompt
Expected savings: 60–70% immediately

Week 2: Kill Heartbeat Costs (15 minutes)
Install Ollama
Pull llama3.2:3b
Update config to use Ollama for heartbeats
Expected savings: $50+/month

Week 3: Add Protection (10 minutes)
Add rate limiting rules to system prompt
Set budget alerts
Test the limits work
Expected savings: Prevents disasters

Week 4: Advanced Optimization (20 minutes)
Enable prompt caching
Organize workspace files
Practice batching similar tasks
Expected savings: $200–400/month for batch work