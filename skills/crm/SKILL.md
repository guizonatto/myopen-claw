---
name: crm
description: "Skill para criar, atualizar e consultar dados sobre conhecidos, clientes, amigos e familiares, utilizando o serviço MCP-CRM."
---
# Skill: CRM - Gerenciamento de Contatos

## Descrição
Skill para criar, atualizar e consultar dados sobre conhecidos, clientes, amigos e familiares, utilizando o serviço MCP-CRM.

- Permite registrar informações detalhadas sobre cada contato.
- Suporta atualizações incrementais e histórico de interações.
- Invoca o MCP-CRM para persistência e consulta dos dados.


- O campo `social_username` (username em redes sociais como LinkedIn, Instagram, Facebook, Twitter, TikTok) é uma entrada válida para identificar contatos.
- Não é necessário saber o `contact_id` do banco para registrar ou atualizar informações.
- Em caso de homônimos (nomes iguais), utilize pelo menos um dos seguintes campos adicionais para garantir a identificação correta:
  - `email`
  - `phone`
  - `social_username`
- Só realize operações se houver pelo menos 95% de certeza sobre a identidade do contato (evite ambiguidade).

## Exemplo de uso
- Criar novo contato: nome, tipo (cliente, amigo, familiar), telefone, email, observações.
- Atualizar informações de um contato existente.
- Consultar histórico de interações com um contato.

## Exemplo de uso com username de rede social
```json
{
  "action": "update",
  "contact": {
    "name": "João Silva",
    "social_username": "@joaosilva",
    "notes": "29/03/2026: João postou sobre novo emprego no LinkedIn."
  }
}
```

## Exemplo de busca diferenciando homônimos
```json
{
  "action": "get",
  "contact": {
    "name": "João Silva",
    "email": "joao@exemplo.com"
  }
}
```

> Sempre que possível, combine dois ou mais campos para garantir a identificação única do contato antes de atualizar ou registrar um acontecimento.

## Payload de entrada
```json
{
  "action": "create|update|get",
  "contact": {
    "name": "Nome do contato",
    "type": "cliente|amigo|familiar|conhecido",
    "phone": "(xx) xxxxx-xxxx",
    "email": "email@exemplo.com",
    "notes": "Observações ou histórico"
  },
  "contact_id": "(para update/get)"
}
```

## Payload de saída
```json
{
  "status": "success|error",
  "contact_id": "id do contato",
  "data": { ...dados do contato... },
  "message": "Mensagem de erro ou sucesso"
}
```

## Observações
- O skill deve ser testado isoladamente, mockando o MCP-CRM se necessário.
- Atualize este SKILL.md sempre que houver mudanças na interface ou exemplos.
