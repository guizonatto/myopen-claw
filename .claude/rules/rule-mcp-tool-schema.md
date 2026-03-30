# ---
description: Regra para definição deinputSchema  em Tools MCP — OpenClaw
alwaysApply: true
# ---

# Regra parainputSchema  em Tools MCP (Model Context Protocol)

## Obrigatório
- Toda Tool (operação registrada via MCP) deve declarar explicitamente o campo `input_schema`.
- O campo `input_schema` deve seguir o padrão JSON Schema v7 (type, properties, required, etc).
- OinputSchema  deve refletir todos os parâmetros esperados pela operação, incluindo tipos e obrigatoriedade.
- Skills textuais (YAML/JSON/MD) devem referenciar operações e parâmetros compatíveis com oinputSchema  da Tool correspondente.

## Boas práticas
- Documente cada parâmetro no campo `description` doinputSchema .
- Use modelos Pydantic para validação interna, mas sempre exponha oinputSchema  como JSON Schema na Tool.
- Teste a validação doinputSchema  com exemplos válidos e inválidos.

## Exemplo
```python
Tool(
    name="add_contact",
    description="Adiciona um novo contato ao CRM.",
   inputSchema ={
        "type": "object",
        "properties": {
            "nome": {"type": "string", "description": "Nome do contato"},
            "email": {"type": "string", "description": "Email do contato"}
        },
        "required": ["nome", "email"]
    }
)
```

## Referências
- docs/openclaw-mcp.md
- https://json-schema.org/understanding-json-schema/
- Pydantic: https://docs.pydantic.dev/latest/usage/schema/
