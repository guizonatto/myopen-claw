---
name: humanizer
description: "Remove padrões de escrita gerada por IA e humaniza textos. Use quando precisar: (1) reescrever texto com tom artificial para soar natural; (2) remover AI-isms como 'tapestry', 'delve', 'pivotal', 'testament', 'landscape', listas com headers em negrito, em-dashes excessivos, conclusões genéricas positivas; (3) adicionar personalidade, ritmo variado e voz humana ao texto; (4) revisar textos antes de publicação (posts, artigos, emails, WhatsApp). Trigger: 'humaniza esse texto', 'remove AI patterns', 'parece robô', 'soa artificial'."
metadata:
  openclaw:
    tools:
      - http: web
        description: Busca Wikipedia para auto-atualização semanal dos padrões
      - bash: git
        description: Commit e push das atualizações de ai-patterns.md
---

# Humanizer

Dois modos: **humanize** (padrão) e **self-update** (disparado pelo cron semanal).

---

## Modo 1 — Humanize

### Processo

1. Ler [ai-patterns.md](references/ai-patterns.md) — catálogo completo dos 24 padrões com exemplos antes/depois
2. Escanear o texto de entrada contra cada categoria de padrão
3. Reescrever as seções problemáticas
4. Verificar checklist de alma (ver abaixo)
5. Entregar o texto humanizado

### Checklist de alma — o texto reescrito deve

- Variar o comprimento das frases (curtas e longas alternadas)
- Ter opinião quando o contexto permite — não apenas reportar fatos de forma neutra
- Usar construções simples: "é", "tem", "faz" no lugar de "serve como", "representa", "boasts"
- Soar natural quando lido em voz alta
- Usar detalhes específicos no lugar de afirmações vagas

### Output

Entregar apenas o texto reescrito. Se o usuário pedir, adicionar lista resumida das mudanças feitas.

---

## Modo 2 — Self-update (cron semanal)

Disparado toda segunda-feira às 06:00 com o prompt: `humanizer self-update`.

### Processo

1. Buscar o conteúdo atual da página Wikipedia:
   `https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing`

2. Comparar com o conteúdo atual de [ai-patterns.md](references/ai-patterns.md)

3. Se houver padrões novos ou alterados:
   - Atualizar `references/ai-patterns.md` com as mudanças
   - Commit e push:
   ```bash
   cd ~/.openclaw/workspace
   git add skills/humanizer/references/ai-patterns.md
   git commit -m "feat(humanizer): sync ai-patterns from Wikipedia — $(date +%Y-%m-%d)"
   git push https://${GITHUB_TOKEN}@github.com/${GITHUB_ORG}/${GITHUB_REPO}.git main
   ```

4. Se não houver mudanças: encerrar silenciosamente.
