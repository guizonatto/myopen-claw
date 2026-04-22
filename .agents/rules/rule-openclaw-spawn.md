# ---
description: Regra para delegação de tarefas com subagentes (sessions_spawn) — OpenClaw
alwaysApply: model_decision
# ---

# Regra para Delegação de Tarefas com Subagentes (sessions_spawn) — OpenClaw

## Contexto
Quando uma skill envolve um fluxo complexo ou processamento em lote (ex: rodar testes em múltiplos arquivos, revisar vários PRs, publicar em etapas), o agente principal não deve executar tudo sequencialmente para evitar bloqueios e perda de contexto.

## Padrão Arquitetural
- Utilize a ferramenta `sessions_spawn` para criar subagentes, cada um responsável por uma tarefa atômica.
- O parâmetro `runtime: "subagent"` deve ser usado para garantir isolamento e atomicidade.
- O prompt passado ao subagente deve ser claro e específico para a tarefa.
- Use `sessions_list` para monitorar o progresso dos subagentes e agregue os resultados ao final.

## Exemplo de Fluxo (Teste em Lote)
1. Para cada arquivo modificado, crie um subagente com `sessions_spawn` e o prompt:  
   “Rode vitest no arquivo X e me retorne se passou.”
2. Monitore todos os subagentes com `sessions_list`.
3. Quando todos finalizarem, agregue e apresente os resultados ao usuário.

## Boas Práticas
- Cada subagente deve ser responsável por uma tarefa única e bem definida.
- Sempre documente o fluxo de spawn e agregação no SKILL.md da skill.
- Evite dependências entre subagentes; cada um deve ser independente.
