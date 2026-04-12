# Template de Página Notion — Release Semanal

**Título:** Release vX.Y.Z — DD/MM/YYYY

## Campos estruturados
- **Data:** DD/MM/YYYY
- **Versão:** vX.Y.Z
- **Novidades:**
  - Item 1
  - Item 2
- **Entregas Jira:**
  - [JIRA-123] Corrigido bug X
  - [JIRA-124] Nova feature Y
- **Links úteis:**
  - [Changelog](url)
  - [Documentação](url)
- **Tags:** release, integração, performance
- **Resumo CEO:**
  Texto objetivo para liderança
- **FAQ Vendas/Suporte:**
  - Pergunta: Resposta
- **FAQ Usuário Final:**
  - Pergunta: Resposta
- **RAG/IA:**
  Contexto factual para IA

---

## Exemplo de payload JSON para API Notion

```json
{
  "parent": {"database_id": "<NOTION_DATABASE_ID>"},
  "properties": {
    "Name": {"title": [{"text": {"content": "Release v2.3.0 — 07/04/2026"}}]},
    "Data": {"date": {"start": "2026-04-07"}},
    "Versao": {"rich_text": [{"text": {"content": "v2.3.0"}}]},
    "Tags": {"multi_select": [{"name": "release"}, {"name": "integração"}]}
  },
  "children": [
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Novidades"}}]}},
    {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": "Integração Discord finalizada"}}]}},
    {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": "Backend otimizado"}}]}},
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Entregas Jira"}}]}},
    {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": "[JIRA-123] Corrigido bug X"}}]}},
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Resumo CEO"}}]}},
    {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Resumo executivo da release..."}}]}},
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "FAQ Vendas/Suporte"}}]}},
    {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": "O que mudou nesta release? Foram adicionadas integrações..."}}]}},
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "FAQ Usuário Final"}}]}},
    {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": "Como ativo a nova funcionalidade? ..."}}]}},
    {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "RAG/IA"}}]}},
    {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Contexto factual para IA..."}}]}}
  ]
}
```

---

> Ajuste os campos conforme a estrutura do seu database Notion. Use este template como referência para padronizar a exportação da skill.
