# MEMORY.md — Sistema de Memória e Relacionamentos do OpenClaw

## Mapa de memória — qual camada usar

| O que guardar | Onde | Como |
|---|---|---|
| Contato (cliente, amigo, familiar) | `mcp-crm` | `add_contact`, `add_memory` |
| Nota pessoal / conhecimento bruto | Vault `/vault/2000-Knowledge/` | `obsidian-cli create` |
| Nota para processar / inbox | Vault `/vault/4000-Inbox/` | `obsidian-cli create` |
| Memória semântica buscável por IA | cortex-mem (memclaw plugin) | via memória automática |
| Regra ou aprendizado do agente | `AGENTS.md` / `TOOLS.md` | editar arquivo |

**Vault = fonte primária de conhecimento pessoal.**
**cortex-mem = índice vetorial do vault (reindexado às 3h).**
**mcp-crm/memories = dados estruturados relacionais (CRM).**

---

Implementado em `openclaw/memory_db.py`. Backend: PostgreSQL + pgvector.

## Modelo de três camadas

```
contatos                  dados estruturados de pessoas (CRM)
  └── contato_id (FK)
contato_relacionamentos   grafo de vínculos entre contatos
memories                  observações, eventos, regras, follow-ups
  ├── contato_id (FK)   → link preciso a um contato cadastrado
  └── entidade (TEXT)   → fallback: tópico, empresa, pessoa não cadastrada
```

---

## Contatos

### Campos

| Campo | Tipo | Descrição |
|---|---|---|
| `nome` | TEXT | Nome completo |
| `apelido` | TEXT | Como você o chama |
| `tipo` | TEXT | cliente · familiar · amigo · colega · parceiro · fornecedor |
| `aniversario` | DATE | Usado pelo cron para alertas automáticos |
| `telefone` / `whatsapp` | TEXT | Canais de contato |
| `email` / `linkedin` / `instagram` | TEXT | Canais digitais |
| `empresa` / `cargo` / `setor` | TEXT | Contexto profissional |
| `notas` | TEXT | Observações livres |
| `ultimo_contato` | TIMESTAMPTZ | Atualizar após cada interação |

### Uso

```python
from openclaw.memory_db import add_contato, update_contato, search_contatos
from openclaw.memory_db import add_relacionamento, get_contexto_contato

# Cadastrar um cliente
joao_id = add_contato(
    nome="João Silva",
    tipo="cliente",
    empresa="Empresa Y",
    cargo="Diretor de TI",
    aniversario=date(1980, 6, 10),
    whatsapp="+5511999990000",
    linkedin="linkedin.com/in/joaosilva",
)

# Cadastrar o filho e registrar o vínculo
pedro_id = add_contato("Pedro Silva", tipo="familiar")
add_relacionamento(pedro_id, joao_id, tipo="filho_de")
add_relacionamento(joao_id, pedro_id, tipo="pai_de")

# Atualizar após uma reunião
update_contato(joao_id, ultimo_contato=datetime.now(timezone.utc),
               cargo="VP de Tecnologia")

# Buscar contatos rapidamente
resultados = search_contatos("silva")

# Ver tudo sobre um contato em uma chamada
ctx = get_contexto_contato(joao_id)
# ctx["contato"]         → dados estruturados
# ctx["relacionamentos"] → Pedro (filho), etc.
# ctx["memorias"]        → observações e fatos
# ctx["follow_ups"]      → lembretes pendentes
```

---

## Relacionamentos entre contatos

Tipos sugeridos: `filho_de` · `pai_de` · `mae_de` · `conjuge_de` · `irmao_de` · `socio_de` · `colega_de` · `trabalha_para` · `cliente_de` · `amigo_de`

O vínculo é direcional: `filho_de(Pedro → João)` ≠ `pai_de(João → Pedro)`.
Adicionar os dois sentidos facilita buscas em qualquer direção.

---

## Memories

### Tipos

| Tipo | Quando usar |
|---|---|
| `episodica` | Eventos com contexto temporal |
| `semantica` | Fatos duráveis sobre entidades |
| `procedural` | Regras e aprendizados operacionais |
| `follow_up` | Lembretes, pontuais ou recorrentes |

### Categorias

| Categoria | Para quê |
|---|---|
| `pessoal` | Família, amigos, vida pessoal |
| `profissional` | Clientes, parceiros, negócios |
| `tendencia` | Mercado, Twitter, LinkedIn |
| `concorrente` | Monitoramento de concorrentes |
| `sistema` | Regras e aprendizados do OpenClaw |
| `conteudo` | Ideias de posts, textos, campanhas |

### Linking: contato_id vs entidade

- **`contato_id`** — quando a memória é sobre um contato cadastrado (preciso, permite join)
- **`entidade`** — quando é sobre um tópico, empresa ou pessoa não cadastrada

### Exemplos por tipo de relacionamento

```python
from openclaw.memory_db import add_memory, get_memory, get_follow_ups, expire_memory

# ── CLIENTE ──────────────────────────────────────────────────────────────────
add_memory("Respondeu positivamente à proposta de março.",
           tipo="episodica", categoria="profissional",
           contato_id=joao_id, importancia=4)

add_memory("Prefere reuniões pela manhã e detesta ligações sem aviso.",
           tipo="semantica", categoria="profissional",
           contato_id=joao_id, importancia=4)

add_memory("Fechar proposta de consultoria.",
           tipo="follow_up", categoria="profissional",
           contato_id=joao_id,
           validade=datetime(2026, 4, 5, tzinfo=timezone.utc), importancia=5)

# ── FAMILIAR ─────────────────────────────────────────────────────────────────
# Pai cadastrado como contato
pai_id = add_contato("Roberto Zonatto", tipo="familiar")

add_memory("Tem pressão alta, toma Losartana 50mg pela manhã.",
           tipo="semantica", categoria="pessoal",
           contato_id=pai_id, importancia=5)

add_memory("Adora assistir futebol, torcedor do Grêmio.",
           tipo="semantica", categoria="pessoal",
           contato_id=pai_id, importancia=3)

# Aniversário do pai — alerta recorrente todo ano
add_memory("Aniversário do pai. Ligar e planejar jantar em família.",
           tipo="follow_up", categoria="pessoal",
           contato_id=pai_id,
           recorrencia="anual", dia_mes=20, mes=7, importancia=5)

# ── AMIGO ─────────────────────────────────────────────────────────────────────
amigo_id = add_contato("Carlos Mendes", tipo="amigo", instagram="@carlosmendes")

add_memory("Gosta de jogar boliche toda sexta-feira.",
           tipo="semantica", categoria="pessoal",
           contato_id=amigo_id, importancia=3)

add_memory("Se conheceram na faculdade em 2010, curso de Administração.",
           tipo="episodica", categoria="pessoal",
           contato_id=amigo_id, importancia=2)

add_memory("Está passando por divórcio desde fevereiro/26. Ser cuidadoso no assunto.",
           tipo="semantica", categoria="pessoal",
           contato_id=amigo_id, importancia=5)

# ── SEM CONTATO CADASTRADO (tópico) ───────────────────────────────────────────
add_memory("IA generativa cresceu 40% no Q1/2026.",
           tipo="semantica", categoria="tendencia",
           entidade="IA Generativa")

# ── CONSULTAS ─────────────────────────────────────────────────────────────────
# Tudo sobre uma pessoa
ctx = get_contexto_contato(amigo_id)

# Só as memórias pessoais de alguém
historico = get_memory(contato_id=amigo_id, categoria="pessoal")

# Follow-ups pendentes de todos
pendentes = get_follow_ups()

# Marcar como concluído
expire_memory(pendentes[0]["id"])
```

### Recorrência

Memórias com `recorrencia = 'anual' | 'mensal' | 'semanal'` são detectadas pelo
cron `crons/memory_followup_cron.py` (roda às 7h) e geram follow-ups automáticos
com alerta via Telegram N dias antes.

---

## Aniversários diretos de contatos

Além das memórias recorrentes, o campo `aniversario` em `contatos` permite
busca nativa no banco:

```python
from openclaw.memory_db import get_aniversarios_proximos

# Contatos com aniversário nos próximos 7 dias
proximos = get_aniversarios_proximos(dias=7)
# [{"nome": "João Silva", "aniversario": date(1980,6,10), "dias_restantes": 3, ...}]
```

---

## Schema resumido

### `contatos`
`id` · `nome` · `apelido` · `tipo` · `aniversario` · `telefone` · `whatsapp` · `email` · `linkedin` · `instagram` · `empresa` · `cargo` · `setor` · `notas` · `ativo` · `ultimo_contato` · `embedding`

### `contato_relacionamentos`
`id` · `contato_id` → `relacionado_id` · `tipo` · `notas`

### `memories`
`id` · `contato_id` (FK) · `entidade` · `tipo` · `categoria` · `conteudo` · `embedding` · `importancia` · `validade` · `recorrencia` · `dia_mes` · `mes` · `acessos` · `ultimo_acesso` · `origem`
