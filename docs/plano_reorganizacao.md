# Reorganização de skills e pipes

## skills/
- trends/
  - twitter_trends.py
  - twitter_trends_browser.py
  - summarize_trends.py
- contatos/
  - contact_briefing.py
- code_organization_rules.py
- repo_maintenance.py
- skill1.py
- skill2.py
- README.md

## pipes/
- trends/
  - daily_trends_report.py
  - daily_trends_report_telegram.py
  - scrape_and_summarize_trends.py
- contatos/
- README.md

## agents/
- clawlito/
- outro_agente/
- base_agent.py

---

Sugestão: mover arquivos relacionados a tendências para skills/trends e pipes/trends, e arquivos de contatos para suas respectivas subpastas. Manter arquivos utilitários e genéricos na raiz de cada pasta.

---

Ações a executar:
- Mover twitter_trends.py, twitter_trends_browser.py, summarize_trends.py para skills/trends/
- Mover contact_briefing.py para skills/contatos/
- Mover daily_trends_report.py, daily_trends_report_telegram.py, scrape_and_summarize_trends.py para pipes/trends/
- Atualizar imports relativos se necessário.

---

# Sistema de busca contextual para o agente

## Objetivo
Permitir que o agente só envie para o modelo o contexto realmente necessário, instanciando mais dados sob demanda.

## Pipeline proposto

1. **Indexação**
   - Indexar e resumir arquivos relevantes (docs, skills, tools, configs).
   - Dividir em blocos pequenos (ex: 20 linhas).

2. **Busca inicial**
   - Ao receber uma pergunta, buscar os trechos mais relevantes usando busca textual ou semântica.
   - Só enviar ao modelo os top-N blocos.

3. **Expansão sob demanda**
   - Se o modelo pedir mais contexto, buscar mais blocos relacionados e reexecutar.

## Exemplo de uso

```python
from openclaw.context_search import ContextIndexer

indexer = ContextIndexer(["docs", "skills", "tools", "configs"])
indexer.indexar_docs()
contexto = indexer.buscar_contexto("como criar skill")
for path, trecho in contexto:
    print(f"Arquivo: {path}\n{trecho}\n---")
```

## Possíveis melhorias
- Trocar busca textual por embeddings (busca semântica)
- Cache dos índices
- Limitar tamanho do input final
- Ajustar dinamicamente o top-N conforme a confiança da resposta

---

Veja também: [INDEX.md](INDEX.md)
