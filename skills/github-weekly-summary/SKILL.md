---
name: github-weekly-summary
description: >
  Gera resumos semanais integrando releases do GitHub e entregas do Jira, com múltiplos formatos (FAQ, CEO, Discord, e-mail, RAG, Notion). Exporta para Notion e envia para Discord. Ideal para relatórios executivos, comunicação com clientes e indexação IA. Usa IA para sumarização e scripts para coleta/distribuição.
---

### Exemplos de canais recomendados para report no Discord
- weekly-report-projects
- changelog
- entregas
- releases
- projetos
- avisos
- suporte
> Sempre prefira canais com nomes claros e voltados para acompanhamento de projetos ou entregas. Se não existir, crie um canal chamado **weekly-report-projects**.

## Regras obrigatórias de report
Sempre envie/resuma as atividades no canal ou página **Weekly Report - Projects** (Discord e/ou Notion). Se não existir, crie antes de enviar para o discord.


# Skill: GitHub + Jira Weekly Summary

## O que faz
- Busca releases semanais do GitHub
- Busca issues finalizadas no Jira
- Gera resumos em múltiplos formatos (FAQ vendas/suporte, FAQ usuário, CEO, Discord, e-mail, RAG, Notion)
- Exporta resumos para Notion (nova página por release)
- Envia resumo para canal Discord
- Usa IA para sumarização dos dados

## Como usar (passo a passo detalhado)
1. **Configure TODAS as variáveis de ambiente obrigatórias:**
  - `GITHUB_TOKEN`: token pessoal do GitHub (precisa ter acesso de leitura aos repositórios)
  - `GITHUB_REPO`: lista de repositórios GitHub separados por vírgula (ex: org1/repo1,org2/repo2)
  - `JIRA_EMAIL`: seu e-mail cadastrado no Jira
  - `JIRA_TOKEN`: API token gerado no Atlassian
  - `JIRA_BASE_URL`: URL base do Jira (ex: https://empresa.atlassian.net)
  - `JIRA_PROJECT_KEY`: chave do projeto Jira (ex: ABC)
  - `NOTION_TOKEN`: token de integração Notion
  - `NOTION_DATABASE_ID`: ID do database Notion
  - `DISCORD_BOT_TOKEN`: token do bot Discord
  - `DISCORD_GUILD_ID`: ID do servidor Discord. O script busca os canais automaticamente e escolhe o canal mais adequado para postar. **Se o canal desejado não existir, crie o canal no Discord antes de rodar a skill.**

2. **Execute o comando principal:**
  - Rode o main.py para iniciar o pipeline completo.
  - O script valida se TODAS as variáveis estão presentes. Se faltar alguma, ele para e mostra o erro.

3. **Fluxo detalhado:**
  1. Busca releases e commits da semana em TODOS os repositórios e branches do GitHub.
  2. Busca issues finalizadas no Jira.
  3. A própria skill chama a função de sumarização.
  4. Exporta o resumo para o Notion (o objeto precisa ter 'properties' e 'children').
  5. Busca os canais do Discord e posta o resumo no canal mais adequado.

4. **Funções principais:**
  - `fetch_weekly_releases_and_commits()`: busca releases e commits de todos os branches/repos.
  - `fetch_weekly_jira_issues()`: busca issues Jira finalizadas.
  - `generate_summaries()`: Use skill de summary que já existe. Gere os resumos nos formatos (skills\github-weekly-summary\references\summary_templates.md) FAQ, CEO, Discord, e-mail, RAG, Notion. O campo 'notion' precisa ser compatível com export_to_notion.
  - `export_to_notion()`: exporta o resumo para o Notion.
  - `send_to_discord()`: busca canais do servidor e posta no canal mais coerente.

5. **Erros comuns e como evitar:**
  - Variável de ambiente faltando: o script para e mostra qual está faltando.
  - generate_summaries não implementada: pipeline quebra, implemente ou plugue uma IA real.
  - Objeto do Notion incompatível: precisa ter 'properties' e 'children'.
  - Canal Discord não encontrado: verifique se o bot está no servidor e tem permissão.

6. **Exemplo de execução:**
  ```bash
  python skills/github-weekly-summary/scripts/main.py
  ```

7. **Dica:**
  - Leia os logs impressos no terminal para saber onde está o erro.

---
Esta skill foi detalhada para ser à prova de erros e fácil de entender. Se algo quebrar, revise as variáveis, permissões e implemente a função de sumarização.


## Scripts
- scripts/fetch_github_releases.py
- scripts/fetch_jira_issues.py
- scripts/generate_summaries.py
- scripts/export_to_notion.py
- scripts/send_to_discord.py

## Templates
Consulte `references/summary_templates.md` para exemplos e estrutura de cada formato.

## Observações
- Não incluir dados sensíveis nos resumos
- FAQ usuário final deve sempre explicar a funcionalidade
- Resumo CEO inclui métricas, entregas Jira e impacto estratégico
- E-mail deve destacar benefícios práticos para o usuário
- RAG detalha funcionalidades para indexação IA
- Notion recebe página estruturada por release

## Exemplos de uso
- Relatório semanal para CEO
- Mensagem automática no Discord
- Página de changelog no Notion
- FAQ para suporte e usuários finais

---
Consulte os scripts e templates para customização avançada.
