# CRM Integration — Usell Sales Workflow

## Operações disponíveis (MCP-CRM)

| Operação | Campos obrigatórios | Campos opcionais |
|---|---|---|
| `add_contact` | `nome`, `email` | `cnpj`, `cnaes`, `whatsapp` |
| `search_contact` | `query` | — |
| `update_contact` | `contact_id` | `pipeline_status`, `stage`, `icp_type`, `nota`, `whatsapp`, `email`, `empresa`, `cargo`, `tipo`, `linkedin`, `instagram`, `setor` |

---

## Campos de pipeline no contato

| Campo | Tipo | Valores | Descrição |
|---|---|---|---|
| `pipeline_status` | enum | `lead` `qualificado` `interesse` `proposta` `fechado` `perdido` | Onde o cliente está no funil |
| `stage` | text livre | ex: `caos_operacional`, `objecao_preco` | Intent da última interação |
| `icp_type` | enum | `A` `B` `Hesitante` | Perfil identificado do lojista |
| `notas` | text | — | Histórico append-only com timestamp |

### Progressão do pipeline_status

```
lead → qualificado → interesse → proposta → fechado
                                           ↘ perdido
```

| Quando mover | Para |
|---|---|
| ICP identificado + dor confirmada | `qualificado` |
| Perguntou "como funciona?" / "quanto custa?" | `interesse` |
| CTA enviado / demo agendada | `proposta` |
| Aceite / link de pagamento enviado | `fechado` |
| Sem resposta longa / desistência explícita | `perdido` |

---

## Fluxo por mensagem recebida

```
Mensagem do lojista
  │
  ├─ search_contact(query=nome_ou_whatsapp)
  │     ├─ encontrou → usar contact_id
  │     └─ não achou → add_contact(nome, whatsapp) → pegar contact_id
  │
  ├─ detectar intent → gerar resposta
  │
  └─ update_contact(
         contact_id,
         pipeline_status,   ← se houve progressão no funil
         stage,             ← intent desta mensagem
         icp_type,          ← se identificado nesta interação
         nota               ← resumo da interação (appendado automaticamente)
     )
```

---

## Exemplo de chamada

```json
// "Cara, fico maluco com os pedidos, respondo 200 msg por dia"
// Intent: caos_operacional → ICP A → pipeline: lead→qualificado

{
  "operation": "update_contact",
  "contact_id": "uuid-do-contato",
  "pipeline_status": "qualificado",
  "stage": "caos_operacional",
  "icp_type": "A",
  "nota": "Relatou caos com pedidos no WhatsApp (200 msg/dia). Labeling aplicado. Próximo: calcular ROI."
}
```

```json
// "Quanto custa a Usell?"
// Intent: curiosidade_ativa → pipeline: qualificado→interesse

{
  "operation": "update_contact",
  "contact_id": "uuid-do-contato",
  "pipeline_status": "interesse",
  "stage": "curiosidade_ativa",
  "nota": "Perguntou sobre preço. Hook enviado. CTA: demo amanhã."
}
```

---

## Regra de notas

`nota` é sempre **appendada** com timestamp automático — nunca sobrescreve o histórico:

```
2026-04-11 14:32: Relatou caos com pedidos. Labeling aplicado.
2026-04-11 15:10: Objeção preço. Reframe ROI: 2 semanas.
2026-04-11 15:45: Perguntou sobre leilão. CTA demo enviado.
```
