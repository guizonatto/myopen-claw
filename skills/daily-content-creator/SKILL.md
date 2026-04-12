---
name: daily-content-creator
description: >
  Pesquisa um tópico definido pelo usuário, gera ideias de conteúdo relevantes e produz um rascunho completo para publicação.
  Use quando o usuário quiser automatizar a criação de conteúdo diário sobre um tema específico (ex: IA, saúde, mercado imobiliário, tecnologia, etc.).
  Executa as etapas: pesquisa de tendências e notícias recentes → geração de ideias → draft completo da melhor ideia → humanização final do texto com a skill `humanize-writing`.
  Pode ser agendado via cronjob para rodar diariamente.
metadata:
  openclaw:
    model: anthropic/sonnet
---

# Skill: Daily Content Creator

## Objetivo
Pesquisar um tópico, identificar o que está em alta, gerar ideias de conteúdo e produzir um rascunho pronto para publicação (LinkedIn, blog, newsletter, etc.).

## Parâmetros de entrada

| Parâmetro | Obrigatório | Descrição |
|---|---|---|
| `topic` | Sim | Tópico principal (ex: "Inteligência Artificial", "Mercado Imobiliário SP") |
| `format` | Não | Formato alvo: `linkedin`, `blog`, `newsletter`, `thread`, `discord` (padrão: `linkedin`) |
| `tone` | Não | Tom: `profissional`, `educativo`, `provocativo`, `inspirador` (padrão: `profissional`) |
| `language` | Não | Idioma do output: `pt-BR`, `en` (padrão: `pt-BR`) |

## Fluxo de execução

### Etapa 1 — Pesquisa (Research)
1. Buscar notícias e conteúdos recentes sobre `topic` usando `browser`.
2. Consultar fontes confiáveis: Google News, Reddit, HackerNews, LinkedIn, newsletters do setor.
3. Identificar:
   - 7 notícias/acontecimentos relevantes das últimas 48h (salvar título + URL de cada uma)
   - 3 tendências emergentes
   - Dores/perguntas frequentes do público sobre o tema
4. Sintetizar os achados em bullet points (máx. 10 itens) — cada item deve ter o link da fonte.

### Etapa 2 — Ideação (Ideas)
Com base na pesquisa, gerar **10 ideias de conteúdo** no formato:

```
IDEIA #N
Título: [headline chamativo]
Ângulo: [perspectiva única ou gancho]
Por que agora: [ligação com algo atual/relevante]
```

Critérios de qualidade para as ideias:
- Ter um ângulo original (não repetir o óbvio)
- Ter relevância imediata (ligada a algo que aconteceu recentemente)
- Ser acionável ou educativo para o público-alvo
- Ter potencial de engajamento alto no formato alvo

### Etapa 3 — Draft base
Selecionar a ideia com maior potencial e produzir um rascunho completo:

#### Para `linkedin`:
- 1 frase de abertura impactante (hook)
- 5-20 parágrafos curtos (máx. 3 linhas cada)
- Call-to-action no final
- 3-5 hashtags relevantes
- Comprimento: 150-300 palavras

#### Para `blog`:
- Título SEO-friendly
- Introdução (problema/gancho)
- 3-4 seções com subtítulos H2
- Conclusão com CTA
- Comprimento: 600-900 palavras

#### Para `newsletter`:
- Subject line (máx. 60 caracteres)
- Preview text (máx. 90 caracteres)
- Corpo: contexto → insight → ação recomendada
- Comprimento: 200-400 palavras

#### Para `discord`:

Discord tem suporte nativo a Markdown. Siga as melhores práticas abaixo.

**Regras de formatação:**
- Use `**negrito**` para destacar termos-chave e números importantes
- Use `> texto` para citações ou insights de destaque
- Use `## Título` para seções (renderiza como header grande)
- Use `:emoji:` estrategicamente — máx. 3 por mensagem, no início de seções
- Quebre em blocos curtos — Discord lê mal textos em parede
- Comprimento ideal: 300–600 caracteres por bloco; use múltiplos blocos se necessário
- Termine com uma pergunta ou CTA que incentive reply no canal

**Exemplo estado da arte:**

```
## 🤖 IA no Brasil — Insight do Dia

**80% das empresas brasileiras usam IA**, mas menos de 20% têm governança real sobre ela.

> "A corrida para adotar IA está criando uma bomba-relógio de riscos invisíveis." — Gartner 2026

O que está acontecendo na prática:
- Agentes autônomos tomando decisões sem auditoria
- Custos de compute fora de controle
- Zero clareza sobre ROI

**A empresa que vencer não será a que adotou mais rápido — será a que adotou com mais controle.**

💬 Sua empresa já tem uma política de governança para IA? Responde aqui.

📰 Fonte: [Gartner — Agentic AI 2026](https://www.gartner.com/...)
```

**Regras adicionais para o canal:**
- Não usar `@everyone` ou `@here`
- Não incluir links sem contexto — sempre explique o que o link é
- Máx. 2000 caracteres por mensagem (limite do Discord)
- Se ultrapassar 2000 chars, dividir em 2 mensagens numeradas: `[1/2]` e `[2/2]`

#### Para `thread` (X/Twitter):
- Tweet 1: hook forte (máx. 280 chars)
- Tweets 2-7: desenvolvimento do argumento
- Tweet final: conclusão + CTA

### Etapa 4 — Humanização final
Antes de entregar o texto final, sempre executar uma passada de humanização usando a skill `humanize-writing`.

Objetivo dessa etapa:
- remover padrões óbvios de escrita de IA
- deixar o texto mais natural e menos "montado"
- preservar significado, fatos, tom e formato alvo
- manter o texto com cara de texto publicável, não de resposta de chatbot

Regras:
- aplicar a humanização ao draft completo, não só ao hook
- não inventar dados, opiniões ou referências novas durante a humanização
- manter CTA, hashtags, estrutura e limites do formato
- se o texto já estiver natural, fazer apenas ajustes mínimos
- entregar no campo `draft` a versão final já humanizada

## Output esperado

```json
{
  "topic": "Inteligência Artificial",
  "date": "2026-04-06",
  "research_summary": [
    {"titulo": "OpenAI lançou atualização de GPT-4 com foco em reasoning", "url": "https://..."},
    {"titulo": "Empresas brasileiras aumentam investimento em IA em 35%", "url": "https://..."}
  ],
  "ideas": [
    {
      "id": 1,
      "title": "Por que sua empresa ainda não usa IA? Os 3 medos que travam a transformação",
      "angle": "Desmistificar barreiras psicológicas de adoção",
      "why_now": "Pesquisa da FGV mostra que 60% das PMEs ainda não adotaram IA"
    }
  ],
  "selected_idea": 1,
  "draft": "...[texto completo do rascunho final já humanizado]...",
  "format": "linkedin",
  "hashtags": ["#InteligenciaArtificial", "#Inovacao", "#Tecnologia"]
}
```

## Observações
- Não inventar dados ou estatísticas — só usar fatos encontrados na pesquisa.
- Sempre incluir ao menos 1 link de fonte no draft final (no rodapé ou inline conforme o formato).
- Se não encontrar notícias recentes, basear as ideias em tendências gerais do tópico.
- Adaptar tom e vocabulário conforme o parâmetro `tone`.
- Todo draft final deve passar pela skill `humanize-writing` antes da entrega.
- Para agendamento diário, usar cronjob OpenClaw com `topic` fixo no comando.

## Referências
- browser
- docs/openclaw-crons.md
