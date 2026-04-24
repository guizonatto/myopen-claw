---
name: discord-sales-sim
description: "Orquestra simulações de vendas no Discord entre sales-sim e sindico-sim via comando textual sim start."
metadata:
  openclaw:
    model: usage-router/groq/llama-3.1-8b-instant
---
# Skill: Discord Sales Simulation

## Objetivo
Executar simulações manuais no Discord usando:
- `sales-sim` (vendedor)
- `sindico-sim` (cliente simulado)
- `sim-control` (orquestrador)

## Comando de entrada
`sim start city=<cidade> stage=<estagio> persona="<perfil_sindico>" [difficulty=<easy|medium|hard>]`

Exemplos:
- `sim start city=sao_paulo stage=lead persona="sindico conservador"`
- `sim start city=campinas stage=qualificado persona="sindica objetiva focada em custo" difficulty=hard`

## Execução obrigatória
1. Validar que o comando começa com `sim start`.
2. Executar o runner:

```sh
python3 /opt/openclaw-bootstrap/workspace/scripts/discord_sales_sim_runner.py \
  --command "<comando_original>" \
  --channel-id "${DISCORD_SALES_SIM_CHANNEL_ID}"
```

3. Se houver `message_id` do evento, incluir:

```sh
--source-message-id "<message_id>"
```

## Regras
- Não escrever em CRM de produção.
- Não compartilhar memória entre `sales-sim` e `sindico-sim`.
- Persistência somente em `SALES_SIM_STORAGE_DIR`.
