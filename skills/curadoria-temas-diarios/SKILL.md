---
name: curadoria-temas-diarios
description: Buscar diariamente, às 09h, as principais notícias e conteúdos dos temas definidos, realizando curadoria e entregando um resumo organizado por tema.
---

## Objetivo
Buscar diariamente, às 09h, as principais notícias e conteúdos dos temas definidos, realizando curadoria e entregando um resumo organizado por tema.


## Temas e Fontes

### Economia Brasil
- Gratuitos: G1, CNN Brasil, R7, Terra, Poder360

### Economia Mundial
- Gratuitos: BBC, Reuters, CNBC, MarketWatch, Investing.com, Yahoo Finance

### Finanças Brasil
- Gratuitos: InfoMoney, Money Times, Seu Dinheiro, Portal do Bitcoin, Investidor10

### Finanças Mundo
- Gratuitos: Reuters Finance, CNBC Markets, Yahoo Finance, Investing.com, CoinTelegraph

### Guerra no Iraque / Internacional
- Gratuitos: BBC, Al Jazeera, Reuters, CNN, Associated Press, DW

### Política Brasil
- Gratuitos: G1, UOL, CNN Brasil, R7, Terra, Poder360

### Política Mundial
- Gratuitos: BBC, Reuters, Al Jazeera, CNN International, DW

### Mundo Condominial Brasil
- Gratuitos: SíndicoNet, Revista Direcional Condomínios, CondoNews, Sindiconline, CondoPlay

### Inteligência Artificial
- Gratuitos: MIT Technology Review (alguns artigos abertos), TechCrunch, Wired, The Verge, VentureBeat, Nature AI (parte aberta), Stanford AI News, HackerNews

### Tecnologia
- Gratuitos: TechCrunch, Wired, The Verge, VentureBeat, Gizmodo, Ars Technica, HackerNews

### Ciência
- Gratuitos: BBC Science, Scientific American (parte aberta), National Geographic, LiveScience, ScienceAlert, DW Science

### Astronomia
- Gratuitos: NASA News, ESA, Space.com, Universe Today, Sky & Telescope, Astronomy.com

### UFO / OVNI (científico)
- Gratuitos: NASA (UAP/UFO releases), ESA, SETI Institute, Scientific American (UFOs com abordagem crítica), BBC Future, DW Science

### Ideias de Negócios / Startups
- Gratuitos: TechCrunch, ProductHunt, AngelList, Crunchbase News, Venture, ProductHunt, Y Combinator's HackerNews (filtro startups)

### Editais de Inovação e Tecnologia
- Gratuitos: FINEP, BNDES, CNPq, Sebrae, Editais Gov (filtro inovação/tecnologia), Startups.com.br (filtro editais)

## Fluxo
1. Para cada tema, buscar notícias nas fontes gratuitas e, se possível, nas parciais.
2. Realizar curadoria, removendo duplicatas e priorizando diversidade de fontes.
3. Gerar resumo estruturado por tema.
4. Output: lista de temas, cada um com manchetes, links e breve resumo.

## Observações
- Não acessar paywall forte.
- Priorizar fontes abertas e confiáveis.
- O agendamento deve ser feito via cronjob OpenClaw para rodar diariamente às 09h.
- A skill pode ser chamada manualmente para testes.

## Exemplo de output
```json
[
  {
    "tema": "Economia Brasil",
    "noticias": [
      {
        "titulo": "Inflação desacelera em março",
        "fonte": "G1",
        "link": "https://g1.globo.com/economia/noticia/2026/03/30/inflacao-desacelera.html",
        "resumo": "O índice de preços ao consumidor variou 0,2% em março..."
      },
      {
        "titulo": "PIB cresce acima do esperado",
        "fonte": "CNN Brasil",
        "link": "https://cnnbrasil.com.br/economia/pib-cresce.html",
        "resumo": "O Produto Interno Bruto brasileiro avançou 1,5%..."
      }
    ]
  },
  {
    "tema": "Inteligência Artificial",
    "noticias": [
      {
        "titulo": "Novo modelo supera GPT-4",
        "fonte": "MIT Technology Review",
        "link": "https://www.technologyreview.com/ai-novo-modelo.html",
        "resumo": "Pesquisadores lançam modelo de IA que supera benchmarks..."
      }
    ]
  }
]
```

## Referências
- docs/openclaw-cronjob.md
- browser