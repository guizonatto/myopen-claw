# Skill: fetch_and_summarize_editais

Monitora editais e subvenções de inovação e gera resumos automáticos.

## Fontes monitoradas
- FINEP: https://finep.gov.br/chamadas-publicas
- Inovativos: https://inovativos.com.br/
- Fundação Araucária: https://www.fappr.pr.gov.br/
- Sebrae Editais: https://sebrae.com.br/editais
- BNDES Garagem: https://www.bndes.gov.br/wps/portal/site/home/onde-atuamos/garagem

## Funcionamento
- Busca os principais editais/subvenções de cada fonte (heurística simples).
- Gera um resumo automático para cada edital.
- Pronto para integração com MCP de negócios.

## Exemplo de saída
```json
[
  {"fonte": "FINEP", "titulo": "Chamada Pública para Startups...", "url": "https://finep.gov.br/chamadas-publicas", "summary": "Resumo automático: 'Chamada Pública para Startups...' é destaque em FINEP."}
]
```
