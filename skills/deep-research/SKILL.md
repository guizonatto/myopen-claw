---
name: deep-research
description: "Pesquisa sistemática e aprofundada sobre qualquer tópico com análise crítica, verificação adversarial e síntese estruturada."
metadata:
  openclaw:
    model: usage-router/mistral/mistral-medium-2508
---

# SKILL: deep-research

## Objetivo
Conduzir pesquisa aprofundada com rigor epistêmico: múltiplas fontes, análise crítica, síntese rastreável e conclusões acionáveis.

## Quando usar
- "Pesquise a fundo sobre [tópico]"
- "Análise completa de [assunto]"
- "Investigue [tópico] em detalhes"
- "Levante informações atualizadas sobre [tema]"
- Qualquer pedido que exija ir além de uma busca simples

## Guia por domínio

### AI / ML
- Verificar múltiplas perspectivas: acadêmica, industry, open-source
- Priorizar benchmarks e métricas de avaliação
- Revisar implementações de código quando disponível (`web_fetch` em GitHub)
- Notar limitações, vieses e considerações éticas
- Fontes prioritárias: arXiv, Papers With Code, Hugging Face Blog, Google DeepMind Blog

### Notícias e eventos atuais
- Restringir buscas aos últimos 30 dias
- Cross-reference em no mínimo 3 fontes independentes
- Separar reportagem de opinião
- Notar situações em evolução — marcar como "estado em: [data]"

### Avaliações técnicas (stack, frameworks, ferramentas)
- Começar pela documentação oficial via `ctx7`
- Verificar experiências da comunidade (GitHub issues, fóruns, Reddit)
- Buscar benchmarks de performance
- Avaliar maturidade: estrelas GitHub, frequência de commits, suporte ativo

### Negócio e estratégia
- Buscar dados de mercado quantitativos
- Revisar análise de concorrentes
- Consultar relatórios de mercado (Gartner, IDC, CB Insights quando disponíveis)
- Considerar múltiplos frameworks (SWOT, Porter, etc.)
- Avaliar fatores de risco explicitamente

### Regulação e compliance
- Priorizar fontes primárias: portais governamentais, Diário Oficial, legislação
- Verificar data de vigência — normas têm prazo
- Buscar interpretações de órgãos reguladores além da lei em si
- Notar divergências entre texto legal e prática regulatória

## Checklist de qualidade (Fase 7d — Reflexão)
Antes de entregar, verificar item a item:

- [ ] Múltiplas fontes autoritativas consultadas (mín. 3 para confiança Alta)
- [ ] Informações recentes incluídas (checar datas — sinalizar se >1 ano)
- [ ] Perspectivas opostas representadas
- [ ] Qualidade das evidências avaliada (score de fonte por claim)
- [ ] Conflitos e contradições explicitados — não resolvidos artificialmente
- [ ] Hipóteses alternativas listadas (ACH)
- [ ] Lacunas de conhecimento catalogadas
- [ ] Implicações práticas identificadas
- [ ] Todas as afirmações factuais com fonte inline
- [ ] Nível de confiança declarado por claim e global
- [ ] Conclusão responde diretamente à pergunta original (BLUF)
- [ ] Metadata de pesquisa presente no relatório

## Metadata de pesquisa (obrigatório no relatório)
```
**Queries usadas:** [lista das queries de web_search executadas]
**Fontes consultadas:** [N]
**Backtrackings:** [N]
**Data:** [YYYY-MM-DD]
**Confiança geral:** Alta | Média | Baixa — [razão em 1 linha]
```

## Output normalizado
Ver formato completo em `agents/researcher/AGENTS.md`.

Campos obrigatórios em todo relatório:
```
título | escopo | data | confiança geral | cobertura | metadata
contexto | achados (com confiança por claim) | ACH | contradições | lacunas | conclusão BLUF | fontes
```

## Iteração quando necessário
| Situação | Ação |
|---|---|
| Informação conflitante | Investigar mais fundo, apresentar múltiplos pontos de vista com fontes |
| Informação insuficiente | Expandir termos de busca, tentar ângulo diferente |
| Sub-tópico complexo | Decompor e pesquisar sistematicamente |
| Informação desatualizada | Buscar fontes mais recentes antes de concluir |
| Lacuna persistente | Declarar explicitamente após 2 tentativas de backtrack |
