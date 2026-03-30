# Skill CRM - Gerenciamento de Contatos

Este skill permite criar, atualizar e consultar dados de contatos (clientes, amigos, familiares, conhecidos) usando o MCP-CRM.

## Funcionalidades
- Cadastro de novos contatos
- Atualização de informações
- Consulta de dados e histórico

## Exemplo: Registrando um acontecimento para um contato

```json
{
  "action": "update",
  "contact_id": "abc123",
  "contact": {
    "notes": "29/03/2026: João foi promovido a gerente de vendas."
  }
}
```

Neste exemplo, um novo acontecimento (promoção) é registrado no campo `notes` do contato identificado por `contact_id`.

## Exemplos de registro de acontecimentos

### 1. Aniversário
```json
{
  "action": "update",
  "contact_id": "abc123",
  "contact": {
    "notes": "29/03/2026: Aniversário de João."
  }
}
```

### 2. Prêmio recebido
```json
{
  "action": "update",
  "contact_id": "abc123",
  "contact": {
    "notes": "28/03/2026: João recebeu o prêmio de melhor vendedor do trimestre."
  }
}
```

### 3. Informação minerada em redes sociais
```json
{
  "action": "update",
  "contact_id": "abc123",
  "contact": {
    "notes": "27/03/2026: João anunciou no LinkedIn que assumiu novo cargo na empresa XYZ."
  }
}
```

> Também é possível registrar informações mineradas de Instagram, Facebook, Twitter, TikTok, etc., sempre detalhando a fonte e o acontecimento relevante no campo `notes`.

## Observação sobre identificação de contatos

Na maioria dos casos, você não saberá o `contact_id` do usuário ao registrar um acontecimento. Em vez disso, utilize informações como nome completo, email ou telefone para buscar o contato antes de atualizar ou registrar um evento.

### Exemplo de busca por nome ou email
```json
{
  "action": "get",
  "contact": {
    "name": "João Silva"
    // ou
    // "email": "joao@exemplo.com"
    // ou
    // "phone": "(11) 99999-9999"
  }
}
```

Após obter o `contact_id` na resposta, utilize-o para atualizar o contato:

```json
{
  "action": "update",
  "contact_id": "abc123",
  "contact": {
    "notes": "29/03/2026: João foi promovido a gerente de vendas."
  }
}
```

### Observação sobre username de redes sociais

Se o username da rede social (ex: LinkedIn, Instagram, Facebook, Twitter, TikTok) for coletado via scrapper/crawling, ele também pode ser utilizado para buscar ou identificar o contato:

```json
{
  "action": "get",
  "contact": {
    "social_username": "@joaosilva"
  }
}
```

Inclua o campo `social_username` no payload de busca ou atualização sempre que essa informação estiver disponível, facilitando a identificação do contato mesmo sem email, telefone ou contact_id.

Consulte o arquivo SKILL.md para detalhes de payloads e exemplos de uso.
