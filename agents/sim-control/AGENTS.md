# AGENTS.md - Sim Control

## Responsabilidade
Orquestrar simulacoes de vendas no Discord entre `sales-sim` e `sindico-sim`.

## Contrato de comando
- Aceitar apenas:
  - `sim start city=<cidade> stage=<estagio> persona="<perfil_sindico>" [difficulty=<easy|medium|hard>]`
- Se o comando estiver invalido, responder com erro curto e 2 exemplos validos.

## Execucao obrigatoria
1. Normalizar e validar comando.
2. Rodar:
   - `python3 /opt/openclaw-bootstrap/workspace/scripts/discord_sales_sim_runner.py --command "<comando_original>" --channel-id "<canal_atual>" --source-message-id "<mensagem_origem>"`
3. Nao simular manualmente conversa sem o runner.

## Red lines
- Nao usar memoria compartilhada entre os agentes da simulacao.
- Nao gravar resultados em tabelas de aprendizado de producao.
- Nao disparar automacoes fora do canal de simulacao.
