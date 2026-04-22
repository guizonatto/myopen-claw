---
name: shopping-tracker
description: "Skill para tracking de lista de compras. Recebe input do usuário sobre itens comprados, destrincha os produtos, salva no banco do MCP de compras, mantém wish list, faz tracking de periodicidade de compra e avisa quando é provável que precise comprar novamente. O MCP aprende com os hábitos do usuário."
metadata:
  openclaw:
    model: usage-router/groq/openai/gpt-oss-20b
---
## Skill: Shopping Tracker

### Descrição
Skill para tracking de lista de compras. Recebe input do usuário sobre itens comprados, destrincha os produtos, salva no banco do MCP de compras, mantém wish list, faz tracking de periodicidade de compra e avisa quando é provável que precise comprar novamente. O MCP aprende com os hábitos do usuário. 

### Responsabilidade
- Receber input do usuário sobre compras realizadas (pode ser texto ou foto de nota fiscal)
- Extrair e normalizar itens comprados
- Salvar compras e wish list via MCP (Model Context Protocol)
- Fazer tracking de periodicidade de compra
- Notificar quando um item deve ser comprado novamente
- Aprender padrões de compra do usuário


### Estrutura
- Arquivo YAML com definição da skill
- Exemplos de uso
- Referências de schema
- Campos suportados: nome, quantidade, unidade, wishlist, preço, loja, marca, volume_embalagem, última compra, média de dias

### Como testar
- Mockar MCP de compras
- Simular entradas de compras e wish list
- Validar tracking e notificações

### Dependências
- MCP: shopping_tracker_mcp

### Autor
- Guilherme Zonatto

---
