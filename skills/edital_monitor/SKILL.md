---
name: edital_monitor
description: "Monitora editais/subvencoes de inovacao e gera resumos."
metadata:
  openclaw:
    model: usage-router/google/gemini-2.5-pro
---

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

## Política de busca
- Use `web_fetch` como caminho padrão para as páginas institucionais listadas.
- Se uma página mudar de endereço, use `web_search` com foco no domínio oficial para reencontrar a listagem correta.
- Use `browser` apenas quando a listagem depender fortemente de JavaScript ou exigir interação mínima.
- Não use Tavily como padrão; reserve-o para exceções em que o conteúdo oficial esteja difícil de localizar.

## Exemplo de saída
```json
[
  {"fonte": "FINEP", "titulo": "Chamada Pública para Startups...", "url": "https://finep.gov.br/chamadas-publicas", "summary": "Resumo automático: 'Chamada Pública para Startups...' é destaque em FINEP."}
]
```
