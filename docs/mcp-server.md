> Consulte também: [docs/openclaw-mcp.md](openclaw-mcp.md) — padrão oficial de Model Context Protocol (MCP) no OpenClaw.

# Template Definitivo Anti-Alucinação para MCP

Quando você expõe uma função de software (Tool) para um Agente de IA (LLM), a IA "lê" a assinatura da função para decidir como e quando usá-la. Se houver brechas de interpretação, a IA tentará adivinhar, enviar parâmetros que não existem, ou forçar lógicas incorretas.

Abaixo está o padrão-ouro (Template Genérico) utilizando a biblioteca `mcp` (em Python via FastMCP) para construir ferramentas blindadas.

## 4 Regras de Ouro na Construção de Ferramentas MCP

> **1. A Descrição (docstring) é o seu Prompt!**
>
> - A IA lê a docstring da sua ferramenta (o texto entre as aspas triplas) para saber o que a ferramenta faz.
> - Não economize palavras ali. Diga exatamente o que a ferramenta altera, os limites, e quando a IA DEVE ou NÃO DEVE acioná-la.
>
> **2. Tipagem Rígida e Fechada (Enums/Literals):**
>
> - Nunca peça uma string livre se as categorias do seu banco são limitadas.
> - Se o status do cliente só pode ser "Ativo" ou "Inativo", force um `Literal` (ou Enum) na assinatura do Python.
> - Se a IA mandar "Pausado", a SDK bloqueia antes de bater no seu banco!
>
> **3. Devolva "String de Correção" em vez de Erro Fatal:**
>
> - Se o Agent enviar um dado inútil ou vazio, não deixe o programa estourar um Stack Trace de SQL.
> - Use blocos try/except e retorne instruções para a IA no próprio return (Ex: "Erro: Nome muito curto. Pergunte ao humano o sobrenome exato antes de tentar salvar novamente.").
>
> **4. Nomeie sem Margem para Interpretação:**
>
> - `save_data()` é um nome ruim. `add_new_person_to_postgres()` é perfeito.

---

## Código Template (Python)

Você pode usar esta estrutura como base para qualquer serviço empresarial ou pessoal que você for plugar no seu OpenClaw.

```python
from typing import Literal, Optional
from pydantic import Field
from mcp.server.fastmcp import FastMCP

# Cria a instância
mcp_gen = FastMCP("Servico-Gerenciador-Generico")

# =========================================================================
# EXEMPLO 1: Leitura Segura (Busca)
# =========================================================================
@mcp_gen.tool()
def retrieve_system_record(
    entity_id: str = Field(description="ID UUID exato do registro. NUNCA tente inventar este ID."),
    entity_type: Literal["contact", "memory", "event"] = Field(
        description="A categoria. Aceita APENAS 'contact', 'memory' ou 'event'."
    )
) -> str:
    """
    Busca um registro no Banco de Dados.
    
    CRITÉRIOS DE USO (ATENÇÃO, AGENTE):
    - NÃO USE isso se você não tiver o entity_id exato. Em vez disso, pergunte ao humano.
    - O resultado retornado deve ser analisado por você e resumido antes de falar com o humano.
    """
    # Lógica Simulada de DB
    if not entity_id or len(entity_id) < 5:
         # <-- A técnica da "Mensagem Educativa"
         return "SISTEMA RECUSOU: O 'entity_id' fornecido é inválido. Pare imediatamente e peça confirmação ao usuário."
         
    return f"[Dados Encontrados] O registro {entity_id} do tipo {entity_type} possui o status de finalizado."

# =========================================================================
# EXEMPLO 2: Escrita Blindada (Inserção/CRUD)
# =========================================================================
@mcp_gen.tool()
def save_important_fact(
    fact_summary: str = Field(description="O fato resumido em no máximo 10 palavras."),
    confidence_level: Literal["alta", "media", "baixa"] = Field(
        description="O grau de certeza sobre este fato. Se o humano estiver incerto, passe 'baixa'."
    ),
    raw_source: Optional[str] = Field(
        default=None, 
        description="A URL de onde tirou a informação. Se foi o humano que falou no chat, omita."
    )
) -> str:
    """
    Salva um fato ou memória vital do humano no banco de dados relacional permanente.
    
    GATILHO DE ATIVAÇÃO:
    - Acione APENAS quando o humano apresentar uma informação que pareça relevante a longo prazo.
    - NÃO use para registrar saudações ou bate-papos irrelevantes.
    """
    try:
        # Aqui iria a sua rotina SQL ...
        # cursor.execute("INSERT ...")
        
        # O Retorno "Positivo" alimenta a IA confirmando que a ação teve impacto no mundo real
        return f"AÇÃO BEM SUCEDIDA: Fato '{fact_summary}' salvo na categoria {confidence_level}. Diga ao usuário que você guardou essa informação."
    
    except Exception as erro:
         # O Retorno "Negativo Educativo"
         return f"FALHA INTERNA DO BANCO: A tentativa falhou ({str(erro)}). Cancele a operação de memória desta vez."

if __name__ == "__main__":
    # Inicializa SSE na porta que será lida no openclaw.config.json
    mcp_gen.settings.host = "0.0.0.0"
    mcp_gen.settings.port = 8500
    mcp_gen.run("sse")
```

---

## O que acontece no cérebro do LLM com esse código?

- **Tipagem Limitada (Literal[]):** Se o modelo tentar inventar um tipo e mandar `entity_type="empresa"`, a própria SDK (via Pydantic) rejeitará o JSON antes de executar o banco! O modelo receberá "Input error: must be contact, memory ou event" e saberá que se perdeu ali mesmo, corrigindo-se sozinho.
- **Field(description=...):** As descrições por campo injetam no prompt do modelo o que ele deve priorizar ao gerar a variável daquela Tool. Se você não coloca instrução nenhuma, a IA adivinha se "summary" deve ser um parágrafo de 5 páginas ou uma linha de 3 palavras.

> Siga religiosamente essa proteção para operações vitais do seu CRM ou banco Postgres.