# Organização recomendada de pastas para o projeto OpenClaw

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

## docs/
- INDEX.md  # Índice mestre da documentação, sempre atualizado via script
- ...outros arquivos markdown

> Sempre rode `python scripts/docs_index_script.py` após mudanças em docs/ para manter o índice atualizado.

---

Sugestão: mover arquivos relacionados a tendências para skills/trends e pipes/trends, e arquivos de contatos para suas respectivas subpastas. Manter arquivos utilitários e genéricos na raiz de cada pasta.

Veja também: [INDEX.md](INDEX.md)
