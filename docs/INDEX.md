
# Índice de Documentação OpenClaw

- [Arquitetura](architecture.md): Visão geral da arquitetura do sistema.
- [Regras Atômicas](atomic_rules.md): Princípios e regras para desenvolvimento.
- [Referência de Configuração](config_reference.md): Todos os parâmetros configuráveis.
- [Decisões de Projeto](decisions.md): Histórico de decisões importantes.
- [Estrutura Recomendada](estrutura_recomendada.md): Como organizar o repositório.
- [Como Criar Skills](how-to-create-skills -in-openclaw.md): Passo a passo para criar novas skills.
- [Referência OpenClaw](openclaw_reference.md): Glossário e conceitos do OpenClaw.
- [Plano de Reorganização](plano_reorganizacao.md): Estratégia para melhorar a documentação.
- [Hooks](hooks-openclaw.md): Sistema de automação por eventos e integrações.
- [Standing Orders](standing-orders-openclaw.md): Autoridade permanente e programas autônomos do agente.
- [Webhooks](webhooks.md): Integração e triggers HTTP externos.

## Manutenção do índice de documentação

Sempre que adicionar, remover ou renomear arquivos em docs/, rode o script de indexação para atualizar o índice:

```sh
python scripts/docs_index_script.py
```

Mantenha títulos claros e descritivos no início de cada arquivo markdown para facilitar a navegação.

### Checklist de Manutenção

- [ ] Rode `python scripts/docs_index_script.py` após mudanças em docs/
- [ ] Mantenha títulos claros nos arquivos markdown
- [ ] Atualize links cruzados entre docs principais
- [ ] Revise docs/estrutura_recomendada.md para incluir INDEX.md
