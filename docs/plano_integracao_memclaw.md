# Plano de Integração: Memória Persistente (Cortex-Mem + MemClaw)

Este plano descreve a integração do **Cortex-Mem** (Long-term Memory Service) com o **OpenClaw Gateway**, utilizando o plugin oficial **@memclaw/memclaw**.

## 1. Arquitetura do Sistema de Memória

A memória será dividida em duas camadas:
1.  **Cortex-Mem (Backend):** Serviço autônomo que gerencia o banco vetorial (Qdrant), faz extração de entidades e busca semântica (RAG).
2.  **MemClaw (Plugin OpenClaw):** Ponte que intercepta as mensagens do Gateway, envia para indexação no Cortex-Mem e recupera contexto relevante antes de enviar para o LLM.

## 2. Configuração da Infraestrutura (Docker)

### Qdrant (Banco Vetorial)
- **Imagem:** `qdrant/qdrant:latest`
- **Porta:** `6333`
- **Volume:** `qdrant-data` para persistência.

### Cortex-Mem (Gerenciador de Memória)
- **Imagem:** `sopaco/cortex-mem:latest`
- **Dependência:** Aguarda `qdrant` estar `healthy`.
- **Variáveis Chave:**
    - `QDRANT_URL`: URL gRPC do Qdrant.
    - `LLM_API_KEY`: Para extração de entidades e sumarização.
    - `EMBEDDING_API_KEY`: Para geração de vetores.

### OpenClaw Gateway
- **Dependência:** Aguarda `cortex-mem` estar ativo.
- **Variável Chave:**
    - `CORTEX_MEM_URL`: URL do serviço (ex: `http://cortex-mem:8085`).

## 3. Configuração do Gateway (openclaw.json)

Para usar o plugin `@memclaw/memclaw`, o `openclaw.json` deve ser configurado assim:

```json
{
  "plugins": {
    "entries": {
      "memclaw": {
        "enabled": true,
        "config": {
          "serviceUrl": "${CORTEX_MEM_URL}",
          "autoStartServices": false,
          "llmApiBaseUrl": "${OPENAI_BASE_URL}",
          "llmApiKey": "${OPENAI_API_KEY}",
          "llmModel": "${OPENAI_MODEL}",
          "embeddingApiBaseUrl": "http://ollama:11435/v1",
          "embeddingApiKey": "ollama",
          "embeddingModel": "${EMBEDDING_MODEL}"
        }
      }
    }
  },
  "agents": {
    "defaults": {
      "memorySearch": {
        "enabled": false
      }
    }
  }
}
```

## 4. Automação no Dockerfile e Entrypoint

Para garantir que o sistema suba configurado "out-of-the-box":

1.  **Dockerfile:** Instalar o plugin `@memclaw/memclaw` durante o build.
2.  **entrypoint.sh:** 
    - Garantir que o volume receba o `openclaw.json` base no primeiro boot.
    - Reafirmar a configuração do `memclaw` após o onboarding do OpenClaw.
    - Não reinstalar o plugin em runtime.

## 5. Variáveis de Ambiente (.env)

| Variável | Valor Exemplo | Descrição |
|----------|---------------|-----------|
| `CORTEX_MEM_URL` | `http://cortex-mem:8085` | Endpoint do serviço de memória |
| `EMBEDDING_MODEL` | `qwen3-embedding:4b` | Modelo de vetorização no Ollama |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Endpoint OpenAI-compatible usado pelo Cortex-Mem para extração/sumarização |
| `OPENAI_API_KEY` | `sk-...` | Chave do backend LLM usado pelo Cortex-Mem |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo para extração e sumarização do Cortex-Mem |

## 6. Próximos Passos (Execução)

1.  [x] **Ajustar Dockerfile:** Instalação do plugin no build.
2.  [x] **Ajustar entrypoint.sh:** Configuração automática do MemClaw sem reinstalação em runtime.
3.  [x] **Atualizar openclaw.json:** `memclaw` ativo e `agents.defaults.memorySearch.enabled = false`.
4.  [ ] **Testar Fluxo:** Verificar se as conversas estão sendo indexadas no Qdrant e recuperadas em novas sessões.

---
*Referência:*
- [OpenClaw Memory Overview](https://docs.openclaw.ai/concepts/memory#memory-overview)
- [Cortex-Mem Repository](https://github.com/sopaco/cortex-mem)
