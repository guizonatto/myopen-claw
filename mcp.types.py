from typing import Any, Dict
from pydantic import BaseModel, Field

class Tool(BaseModel):
    name: str = Field(..., description="Nome da operação exposta pela Tool.")
    description: str = Field(..., description="Descrição da operação exposta pela Tool.")
    inputSchema: Dict[str, Any] = Field(..., description="Schema de input no padrão JSON Schema v7.")

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True
        schema_extra = {
            "example": {
                "name": "add_contact",
                "description": "Adiciona um novo contato ao CRM.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string", "description": "Nome do contato"},
                        "email": {"type": "string", "description": "Email do contato"}
                    },
                    "required": ["nome", "email"]
                }
            }
        }

    def to_dict(self) -> dict:
        """Serializa a Tool para dict."""
        return self.dict()
