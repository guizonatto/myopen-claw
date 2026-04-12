# Skill: fetch_and_summarize_politics_economy

Monitora fontes de política e economia (nacional e internacional) e gera resumos automáticos.

## Fontes monitoradas
### Política
- JOTA: https://www.jota.info/
- Nexo Jornal: https://www.nexojornal.com.br/
- NYT World: https://www.nytimes.com/section/world
- BBC News Mundo: https://www.bbc.com/portuguese/internacional

### Economia
- Brazil Journal: https://braziljournal.com/
- Valor Econômico: https://valor.globo.com/
- Bloomberg: https://www.bloomberg.com/
- Financial Times: https://www.ft.com/

## Funcionamento
- Busca as principais manchetes de cada fonte (heurística simples).
- Gera um resumo automático para cada notícia.
- Pronto para integração com MCP de negócios.

## Exemplo de saída
```json
[
  {"fonte": "JOTA", "titulo": "Nova lei impacta startups...", "url": "https://www.jota.info/", "summary": "Resumo automático: 'Nova lei impacta startups...' é destaque em JOTA."}
]
```
