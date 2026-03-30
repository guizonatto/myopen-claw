---
title: Manutenção do Repositório OpenClaw
summary: Skill para registrar e lembrar regras e decisões de manutenção do repositório.
applyTo: [".agents/repo_maintenance.py"]
---

# Instruções
- Sempre documentar decisões importantes em docs/decisions.md.
- Atualizar o README.md após mudanças estruturais.
- Adicionar novas skills e tools em seus respectivos diretórios.
- Registrar aprendizados e problemas recorrentes no MEMORY (banco de dados).
- Referenciar arquivos em docs/ sempre que uma regra ou decisão precisar de detalhamento extra.

# Exemplo de uso
Execute a skill para registrar as regras no banco de memória:

```python
from .agents import repo_maintenance
repo_maintenance.run()
```
