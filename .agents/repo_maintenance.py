"""
Skill: repo_maintenance
Função: Automatiza e documenta decisões e regras para manter o repositório OpenClaw organizado e atualizado.
"""
from openclaw.memory_db import add_memory

RULES = [
    "Sempre documentar decisões importantes no diretório docs/decisions.md.",
    "Atualizar o README.md após mudanças estruturais.",
    "Adicionar novas skills e tools em seus respectivos diretórios.",
    "Registrar aprendizados e problemas recorrentes no MEMORY (banco de dados).",
    "Referenciar arquivos em docs/ sempre que uma regra ou decisão precisar de detalhamento extra."
]

def run():
    for rule in RULES:
        add_memory("repo_rule", rule)
    print("Regras de manutenção do repositório registradas no MEMORY.")
