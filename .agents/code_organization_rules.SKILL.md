---
title: Manter o código organizado
summary: Checklist e workflow para garantir a organização, clareza e manutenção do código no projeto OpenClaw.
applyTo: [".agents/code_organization_rules.py"]
---

# Objetivo
Garantir que o código do projeto OpenClaw permaneça limpo, modular, documentado e fácil de manter, seguindo boas práticas e decisões do time.

# Passos do Workflow
1. Implemente cada nova funcionalidade como uma skill ou tool separada.
2. Documente toda skill/tool em SKILL.md ou TOOLS.md, incluindo parâmetros e exemplos de uso.
3. Atualize o AGENTS.md sempre que um novo fluxo de operação for criado ou alterado.
4. Mantenha o código limpo, modular e com comentários explicativos quando necessário.
5. Adicione testes automatizados para skills críticas.
6. Registre decisões de arquitetura e padrões em docs/decisions.md.
7. Evite duplicidade de código: reutilize funções e módulos sempre que possível.
8. Inclua instruções de uso e exemplos no README.md para cada componente novo.
9. Skills e tools devem ser carregadas dinamicamente pelo agente, facilitando extensibilidade.
10. Faça revisão periódica dos diretórios skills/, tools/, workflows/ e configs/ para garantir organização.

# Critérios de Qualidade
- Toda nova skill/tool está documentada.
- Não há código duplicado.
- README.md e AGENTS.md estão atualizados.
- Decisões importantes estão em docs/decisions.md.
- Testes automatizados cobrem skills críticas.

# Exemplo de uso
Execute a skill para registrar as regras no banco de memória:

```python
from .agents import code_organization_rules
code_organization_rules.run()
```

# Sugestão de customização
- Adicione validações automáticas para detectar código duplicado ou falta de documentação.
- Crie um checklist de revisão de PR baseado nessas regras.
