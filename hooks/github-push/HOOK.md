---
name: github-push
description: "Commita e faz push das alterações do workspace para o GitHub ao receber command:stop"
metadata:
  {
    "openclaw": {
      "emoji": "⬆",
      "events": ["command:stop"],
      "requires": {
        "bins": ["git"],
        "env": ["GITHUB_TOKEN", "GITHUB_ORG", "GITHUB_REPO"]
      }
    }
  }
---

# GitHub Push Hook

Faz `git add`, `git commit` e `git push` do workspace ao final de cada sessão (`/stop`).

## Variáveis de ambiente necessárias

- `GITHUB_TOKEN` — Personal Access Token com escopo `repo`
- `GITHUB_ORG` — organização ou usuário (ex: `guizonatto`)
- `GITHUB_REPO` — nome do repositório (ex: `myopen-claw`)
