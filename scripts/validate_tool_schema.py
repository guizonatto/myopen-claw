import json
from jsonschema import validate, Draft7Validator, ValidationError
from typing import Dict, Any

# Exemplo de schema mínimo para Tool
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "input_schema": {"type": "object"}
    },
    "required": ["name", "description", "input_schema"]
}

def validate_tool_schema(tool: Dict[str, Any]) -> None:
    """Valida se o dicionário tool segue o JSON Schema Draft 7 para Tool."""
    validator = Draft7Validator(TOOL_SCHEMA)
    errors = sorted(validator.iter_errors(tool), key=lambda e: e.path)
    if errors:
        for error in errors:
            print(f"Erro de schema: {error.message}")
        raise ValidationError("Tool não está conforme o schema Draft 7.")
    print("Tool schema válido!")

# Exemplo de uso:
if __name__ == "__main__":
    # Exemplo de Tool válido
    tool = {
        "name": "add_contact",
        "description": "Adiciona um novo contato ao CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "email": {"type": "string"}
            },
            "required": ["nome", "email"]
        }
    }
    validate_tool_schema(tool)
