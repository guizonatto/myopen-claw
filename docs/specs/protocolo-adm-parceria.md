# Spec: Protocolo de Parceria com Administradoras (zind-crm-cold-contact-adm)

**Status:** rascunho — pendente de implementação completa  
**Agente:** `agents/zind-crm-cold-contact-adm/`  
**Data:** 2026-05-06

---

## Contexto do negócio

A administradora **não é o cliente final da Zind** — ela é um **canal de distribuição**.  
A lógica de valor é:
- A Zind ajuda os síndicos que a administradora gerencia a ficarem mais organizados
- Síndico organizado → menos retrabalho para a administradora (menos ligações, menos cobranças manuais)
- A administradora ganha reputação e diferencial ao "oferecer" a ferramenta para seus clientes
- A Zind cresce o base de usuários sem precisar abordar cada síndico individualmente

**Modelo de parceria:**
- Administradora indica a Zind para seus síndicos gerenciados
- URL exclusiva: `zind.pro/parceria` (landing page de conversão com formulário)
- Possibilidade de reunião com fundador para discutir termos
- Termos de comissão / co-branding: **a ser definido pelo time comercial humano**

---

## Fluxo principal (4 ações — WhatsApp)

### Ação 1 — Abertura (0 eventos)
> "Oi! Sou o Rafa da Zind (zind.pro). A gente tem uma proposta de parceria para administradoras — ajuda seus síndicos e gera valor pra vocês também. Tem 2 min?"

Objetivo: despertar curiosidade sem revelar o produto. PARE e aguarde resposta.

### Ação 2 — Benefício central (1 evento, resposta positiva)
> "Síndicos que usam a Zind ficam mais organizados e dependem menos da administradora para tarefas operacionais. Isso reduz retrabalho dos dois lados."

Objetivo: mostrar o ganho PARA A ADMINISTRADORA, não para o síndico.

### Ação 3 — Link exclusivo (2 eventos)
> "Preparei uma página exclusiva pra administradoras: zind.pro/parceria. Tem os detalhes e dá pra já solicitar a parceria por lá."

Objetivo: direcionamento para auto-conversão. Sem pitch verbal longo.

### Ação 4 — CTA reunião (3 eventos)
> "Faz sentido batermos um papo de 15 min com nosso fundador para ver como encaixar isso no fluxo de vocês?"

Objetivo: micro-compromisso de baixo custo para reunião de definição de parceria.

---

## Cenários especiais a implementar

### A. Gatekeeper — recepcionista ou assistente
**Situação:** quem atende não tem poder de decisão sobre parcerias.  
**Comportamento esperado:**
- Perguntar quem é responsável pela área de parcerias ou de tecnologia
- Script: "Quem cuida de parcerias tecnológicas aí? Gostaria de falar com a pessoa certa."
- Se não souber: "Pode me passar o contato de quem cuida disso?"
- Registrar novo contato se fornecido (Etapa 1D, igual ao protocolo síndico)

### B. Pedido de e-mail com proposta
**Situação:** "Pode mandar um e-mail explicando?"  
**Comportamento esperado:**
1. Confirmar o e-mail do interlocutor
2. Mencionar que já existe material online: "Tem tudo em zind.pro/parceria — mais rápido do que e-mail!"
3. Se insistir no e-mail: registrar o e-mail no CRM via `update_contact` e sinalizar para humano enviar
4. **Não enviar e-mail diretamente** — gerar handover para time comercial
5. Script de confirmação: "Anotei! Nosso time vai mandar nos próximos dias. Posso já te mostrar a página enquanto isso?"

**Pendência:** definir template de e-mail de parceria e remetente oficial

### C. "Já temos parceria com outra empresa"
**Situação:** administradora menciona um produto concorrente.  
**Comportamento esperado:**
- Não citar o concorrente pelo nome
- Explorar o gap: "Que tipo de funcionalidade você sente falta na solução atual?"
- Posicionar a Zind como complementar, não substituta: "A Zind foca no lado do síndico profissional — pode ser que se complementem."
- Script: "Entendo! O que você ainda sente falta na solução que vocês têm hoje?"

### D. Decisão em comitê / múltiplos aprovadores
**Situação:** "Vou precisar passar pelo sócio / diretoria antes."  
**Comportamento esperado:**
- Não pressionar. Oferecer material para facilitar a apresentação interna.
- Script: "Faz sentido! Posso mandar o link da parceria pra você já ter o material quando for conversar com eles?"
- Agendar follow-up explícito: "Quando seria um bom momento pra eu dar um retorno?"
- Registrar data de follow-up no CRM

### E. Pedido de contrato formal / proposta comercial
**Situação:** "Me manda uma proposta formal."  
**Comportamento esperado:**
- Não enviar contrato — redirecionar para reunião com fundador
- Script: "Os termos variam conforme o perfil da administradora. Fica mais fácil a gente alinhar numa call rápida de 15 min com nosso fundador — aí ele já tira as dúvidas e passa os números certos pra vocês."
- Se insistir em proposta escrita: gerar handover para time comercial humano

### F. Reativação (administradora que não respondeu)
**Situação:** contato anterior sem resposta há X dias.  
**Comportamento esperado:**
- Script: "Oi! Passando pra ver se faz sentido conversarmos sobre a parceria Zind. Ainda é algo relevante pra vocês?"
- Único bloco. Pergunta binária. Sem pressão.

---

## Dados a coletar no CRM durante o fluxo

| Campo | Quando coletar |
|---|---|
| Nome do responsável por parcerias | Ação 1 ou gatekeeper |
| E-mail | Cenário B |
| Número de síndicos gerenciados | Ação 2 (contexto de escala) |
| Software atual usado | Cenário C |
| Data de follow-up | Cenário D |
| Interesse na reunião (sim/não) | Ação 4 |

---

## Integrações pendentes

- [ ] Landing page `zind.pro/parceria` — confirmar URL final
- [ ] Template de e-mail de parceria — definir com marketing
- [ ] Comissão / modelo de co-branding — definir com fundador
- [ ] Orquestrador: adicionar rota `greeting_adm` → `zind-crm-cold-contact-adm`
- [ ] `openclaw.json`: registrar agente
- [ ] `model-stack.json`: optional pin de modelo para ADM
- [ ] Battlecards ADM: criar `skills/crm/library/battlecards_adm.json`

---

## Distinção do protocolo síndico

| Ponto | Síndico profissional | Administradora |
|---|---|---|
| Interlocutor | Decisor direto | Pode ser gatekeeper |
| Objetivo final | Venda SaaS | Parceria de distribuição |
| CTA principal | 10 min com fundador | 15 min + zind.pro/parceria |
| Objeção mais comum | Custo / tempo | "Já temos solução" / comitê |
| Ciclo de decisão | Curto (1 pessoa) | Médio (pode envolver sócios) |
| Canal de conversão | WhatsApp direto | E-mail + reunião |
