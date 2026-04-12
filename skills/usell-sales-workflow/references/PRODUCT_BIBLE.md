# A Bíblia do Vendedor Usell: Edição Especialista de Produto
*Fonte única de verdade técnica. Use quando o lojista fizer perguntas detalhadas sobre como o produto funciona.*

---

## 1. Módulo de Rifas (Engenharia de Sorteio)

- **Capacidade:** 100 a 1.000.000 números por rifa
- **Segurança (Provably Fair):** Algoritmo de Hash Público — segredo criptografado gerado antes do sorteio, auditável na Blockchain
- **Automação:** Reserva instantânea no momento da escolha. Pagamento PIX não detectado em X min (configurável) → número volta ao estoque automaticamente
- **Landing Page:** Cada rifa gera página exclusiva, mobile-first, com barra de progresso em tempo real (escassez visual)

---

## 2. Inteligência de Pré-Venda (Antecipação Estratégica)

- **Agendamento Progressivo:** Mensagens de "Spoiler" disparadas em horários de pico de audiência nos grupos
- **Links de Acesso Antecipado:** Links únicos para clientes VIP (tags CRM) acessarem a sacola 1h antes do público geral
- **Reserva em Trânsito:** Permite vender estoque que ainda está saindo do fornecedor — otimiza fluxo de caixa

---

## 3. Flash Sales / Vendas Relâmpago (Motor de Escassez)

- **Inventory Lockdown:** Item travado por 5 min exclusivos no checkout. Se não fechar → pula para próximo interessado em milissegundos
- **Cronômetros em Tempo Real:** Sincronizados via WebSockets. Exibe "7 pessoas com este item no carrinho agora"
- **Checkout Expresso:** Integração com carteiras digitais — fechamento em 2 cliques

---

## 4. Gestão do Fluxo Automático (Máquina de Estados)

### Motor de Leitura (NLP Lite)
IA processa milhares de mensagens/min identificando variações de intenção: "eu quero", "reserva p mim", "lance 50", "pago".

### Ciclo de vida do pedido (Order Lifecycle)

| Estado | O que acontece |
|---|---|
| `RESERVED` | Estoque bloqueado + link de pagamento enviado |
| `PAID` | Confirmado via Webhook bancário (Baixa Automática) |
| `SEPARATION` | Notificação automática para time de estoque |
| `SHIPPING` | Código de rastreio enviado via WhatsApp |

- **Escala:** Gerencia até 50 grupos simultaneamente com a mesma inteligência

---

## 5. Relatórios de Vendas (BI de Alta Performance)

- **Real-Time:** Dashboard processa GMV, Lucro Líquido (descontando taxas e frete) e Ticket Médio sem latência
- **Filtros:** Por Coleção, por Evento ou por Período Customizado
- **Exportação:** CSV pronto para contabilidade ou integração com ERPs

---

## 6. Relatório Melhores Compradores (Algoritmo de Pareto)

- **LTV Ranking:** Analisa todo o histórico transacional e cria ranking de Lifetime Value
- **Recorrência:** Identifica compradores semanais vs. compradores únicos
- **Ação direta:** Botão "Enviar Convite VIP" ou "Dar Cupom Especial" para o Top 1%

---

## 7. CRM Especialista

- **Histórico Atômico:** Linha do tempo de cada item comprado, devolvido ou cancelado nos últimos 24 meses
- **Carteira de Créditos/Trocas:** Crédito de devolução vinculado ao telefone, aplicado automaticamente na próxima compra via WhatsApp
- **Indexação por Telefone:** Reconhecimento pelo número WhatsApp — sem login ou senha

---

## 8. Sistema de Envio & The Vault (A Sacola)

- **Ciclo de Sacola:** Lojista define período (ex: seg–sex). Todos os pedidos da mesma cliente consolidados em um pacote
- **Bulk Shipping:** Integração Melhor Envio/Correios — etiquetas em lote, economia de até 15 min por pacote
- **Mensagem de incentivo:** "Você já tem 3 itens na sacola. Adicione mais um e ganhe frete grátis na consolidação de amanhã!"

---

## 9. Leilões — Em breve (Gamificação)

- **Bid Increment Logic:** Incrementos mínimos configuráveis (R$ 5, R$ 10). Lances menores rejeitados automaticamente no chat
- **Sniper Protection:** Lance nos últimos 30s → cronômetro volta para 60s (garante valor máximo de mercado)
- **Vencedor Automático:** Bot marca vencedor, parabeniza no grupo e envia link de pagamento no privado

---

## Regra de Ouro

> "Se o lojista perguntar se o sistema aguenta o volume dele: **A Usell foi construída para a escala.** Processamos de 1 a 10.000 pedidos com a mesma precisão cirúrgica."
