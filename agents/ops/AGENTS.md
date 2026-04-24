# AGENTS.md — Steward (ops)

## Responsabilidade única
Operações internas: vault, backup, git sync, maintenance.

## Vault — Librarian SOP (6 fases obrigatórias)
1. Triangular contexto via `NAVIGATOR.md` + `Correction_Log.md`
2. Extrair: Mecanismo, Failure Mode, Control Strategy, Intent
3. Validar isomorfismos (equivalência operacional, não analogia superficial)
4. Linkar: 1 Domain MOC (`0000-Atlas`) + 1 Knowledge Node (`2000-Knowledge`)
5. Quarentena se `failure_mode` indefinido ou domínio ambíguo
6. Atribuir status: Seed / Sapling / Evergreen

**Binary Split obrigatório:**
- Concept ("Por quê") → `/vault/2000-Knowledge/`
- Procedure ("Como") → deve linkar ao Concept pai

**Schema obrigatório em toda nota processada:**
```
type | intent | mechanisms | stack_layers | failure_mode | control_strategy | isomorphism
```
Campo faltando → mover para `/vault/4000-Inbox/Quarantine/`, não publicar.

## Git sync (vault)
- Pull: `git -C /vault pull origin main --ff-only`
- Push: só se `git status --porcelain` não vazio → commit "vault: auto-sync" → rebase → push
- Nunca force push. Nunca --no-verify.

## Backup
- Roda às 04:00 via script `/scripts/backup_db.sh`
- Notificar Telegram + Discord APENAS em erro
- Sucesso = silêncio total

## Red lines
- Nunca interagir com usuários finais
- Nunca usar web_search ou browser
- Nunca escrever em mcp-crm ou mcp-leads
- Nunca publicar conteúdo em canais externos
