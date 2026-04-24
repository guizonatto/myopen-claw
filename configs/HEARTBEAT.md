# HEARTBEAT.md

> Este arquivo define tarefas periódicas para o OpenClaw verificar e agir.

---

## Tarefas de Verificação

### Verificar Inbox
- **Prompt**: "Há arquivos não processados em 4000-Inbox?"
- **Ação**: Processar notas automaticamente.
- **Status**: Ativo ✅

### Verificar Git
- **Prompt**: "Há mudanças não sincronizadas no vault?"
- **Ação**: Fazer `git add`, `commit` e `push` automaticamente.
- **Status**: Ativo ✅

### Verificar Sistema
- **Prompt**: "O Librarian_SOP e Storage_Protocol estão atualizados?"
- **Ação**: Notificar se houver mudanças.
- **Status**: Ativo ✅

---

## Novas Tarefas
- Adicione novas tarefas de verificação aqui conforme necessário.