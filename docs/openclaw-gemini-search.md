# OpenClaw — Gemini Search

> **Resumo:**
> OpenClaw suporta modelos Gemini com grounding do Google Search, retornando respostas AI com citações de resultados ao vivo do Google.

---

## Como obter uma API Key

1. **Crie uma chave**
   - Acesse o [Google AI Studio](https://aistudio.google.com/) e crie uma API key.
2. **Armazene a chave**
   - Defina a variável `GEMINI_API_KEY` no ambiente do Gateway **ou**
   - Configure via comando:
     ```sh
     openclaw configure --section web
     ```

Alternativa: coloque a chave no arquivo `~/.openclaw/.env` para instalações gateway.

---

## Exemplo de configuração

```jsonc
{
  "plugins": {
    "entries": {
      "google": {
        "config": {
          "webSearch": {
            "apiKey": "AIza...", // opcional se GEMINI_API_KEY estiver setada
            "model": "gemini-2.5-flash" // padrão
          }
        }
      }
    }
  },
  "tools": {
    "web": {
      "search": {
        "provider": "gemini"
      }
    }
  }
}
```

---

## Funcionamento

- Diferente de provedores tradicionais (que retornam links/snippets), Gemini usa grounding do Google Search para gerar respostas AI com citações inline.
- O resultado inclui a resposta sintetizada **e** as URLs das fontes.
- URLs de citação são automaticamente resolvidas de redirects do Google para URLs diretas.
- Resolução de redirect usa SSRF guard (HEAD, validação http/https, bloqueio de destinos internos).

---

## Parâmetros suportados

- `query` (obrigatório)
- `count` (opcional)
- **Não suporta:** filtros como país, idioma, freshness, domain_filter.

---

## Seleção de modelo

- Modelo padrão: `gemini-2.5-flash` (rápido e econômico)
- Qualquer modelo Gemini com suporte a grounding pode ser usado via:
  - `plugins.entries.google.config.webSearch.model`