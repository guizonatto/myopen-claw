# Regra para definição e versionamento de cronjobs no OpenClaw



## Estrutura
- Todos os cronjobs devem ser definidos na pasta `crons/`.
- Cada cronjob deve ter um arquivo Python (para APScheduler) ou um arquivo YAML/JSON (para jobs declarativos via CLI/API).
- O comando de criação do cronjob (exemplo: `openclaw cron add ...`) deve ser documentado em um arquivo `.cron.md` ou `.cron.yaml` correspondente na pasta `crons/`.
- O arquivo `.cron.md` deve conter **apenas o comando** (sem comentários, descrições ou metadados extras). Nenhuma informação adicional deve ser incluída.
- Todos os comandos de cronjob devem ser criados, revisados e padronizados a partir de `docs/openclaw-crons.md`, que é o mastermind canônico do projeto para automação de cron jobs.
- O Dockerfile e/ou docker-compose.yml do projeto deve garantir que todos os cronjobs definidos em `crons/` sejam incluídos no build/deploy.
- **Sempre que possível, utilize variáveis de ambiente (.env) para campos sensíveis ou configuráveis (ex: IDs de canal, timezone, tokens) nos comandos dos cronjobs. Use sempre TELEGRAM_CHANNEL_ID para todos os jobs que enviam para o Telegram, evitando múltiplas variáveis para canais diferentes.**

## Boas práticas
- Sempre documente o propósito, agendamento, canal e mensagem do cronjob no arquivo.
- Use nomes descritivos para os arquivos e para o campo `--name` do cronjob.
- Versione toda alteração de cronjob via git.
- Para jobs que disparam skills, a mensagem deve indicar claramente qual skill será executada.
- Sempre referencie a documentação oficial: https://docs.openclaw.ai/automation/cron-jobs / docs/openclaw-crons.md para criar os crons.
- Crons devem ser adicionados em /crons.
- Crons, ao serem criados, devem ser adicioandos ao dockerfile para serem criados no deploy.