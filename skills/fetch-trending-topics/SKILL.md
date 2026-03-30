---
name: x-trending
description: "Use esta skill quando o usuário pedir para verificar os trending topics no X (Twitter). Ela detalha como usar a ferramenta 'browser' interna do OpenClaw para extrair as tendências da rede social de forma autônoma."
---

# X (Twitter) Trending Topics Crawler

Esta skill instrui o agente a utilizar a ferramenta interna `browser` do OpenClaw para acessar o X, lidar com a interface web da plataforma e coletar os assuntos que estão em alta.

## O Fluxo Perfeito do Automator

Quando for acionado para rodar esta skill, siga rigorosamente as etapas abaixo usando apenas a ferramenta `browser`:

### 1. Navegação Inicial
Ordene o navegador a acessar a aba de tendências globais:
* **action**: `goto`
* **url**: `https://x.com/explore/tabs/trending`

### 2. Tratamento de Login e Cookies do X (MUITO IMPORTANTE)
O X bloqueia bots e visualizações anônimas. Pare para analisar a página via DOM ou `screenshot`.
Se a captura tela ou o HTML revelar que fomos redirecionados para uma tela de "Login / Entrar":
* **Pare a execução.**
* Peça gentilmente ao usuário o seu cookie de autenticação ("auth_token").
* Ensine o usuário a pegar esse dado passo-a-passo:
  > *"Preciso do seu cookie de acesso. Abra o X/Twitter no seu navegador real (Chrome/Edge), aperte F12 para abrir o modo desenvolvedor, e vá na aba 'Application' (Aplicativo). Na barra lateral esquerda procure por Cookies > https://x.com. Procure na tabela o nome `auth_token`, copie o valor dele e cole aqui no chat pra mim!"*
* Quando o usuário te dar o valor, grave nas suas Memórias com a ferramenta `memory_save` (ou oriente que ele ponha num `.env` se for rodar script Bash).

### 3. Extração Limpa de Dados
Assim que confirmar que a página carregou as caixas de tendências:
* **action**: `get_dom` ou `extract_text`
* Concentre-se apenas na árvore do DOM que possui os textos principais. O X geralmente guarda os trendings nas divs principais em modo lista.

### 4. Apresentação (Output)
Não jogue o código sujo HTML para o usuário. 
Se você obteve sucesso lendo as tendências, escreva uma mensagem estilizada contendo uma tabela ou uma lista usando a ferramenta `summarize` para organizar os dados. A estrutura ideal é:
- Posição (Ex: 1)
- Tópico em si (O Assunto)
- Contagem de posts ou Categoria (Ex: 25.5k posts | Esportes)
- resumo curto do que é o tópico (Ex: "O que é isso? Por que está em alta?")

Pronto! Se ocorrer qualquer fechamento ou erro no browser, reporte o erro fatal para o usuário de forma amigável.
