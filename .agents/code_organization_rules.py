"""
Skill: code_organization_rules
Função: Registrar e lembrar regras para organização do código no projeto OpenClaw.
"""
from openclaw.memory_db import add_memory

RULES = [
    "Cada nova funcionalidade deve ser implementada como uma skill ou tool separada.",
    "Documente toda skill/tool em SKILL.md ou TOOLS.md, incluindo parâmetros e exemplos de uso.",
    "Atualize o AGENTS.md sempre que um novo fluxo de operação for criado ou alterado.",
    "Mantenha o código limpo, modular e com comentários explicativos quando necessário.",
    "Adicione testes automatizados para skills críticas.",
    "Registre decisões de arquitetura e padrões em docs/decisions.md.",
    "Evite duplicidade de código: reutilize funções e módulos sempre que possível.",
    "Inclua instruções de uso e exemplos no README.md para cada componente novo.",
    "Skills e tools devem ser carregadas dinamicamente pelo agente, facilitando extensibilidade.",
    "Faça revisão periódica dos diretórios skills/, tools/, workflows/ e configs/ para garantir organização."
]

def run():
    for rule in RULES:
        add_memory("code_rule", rule)
    print("Regras de organização do código registradas no MEMORY.")
