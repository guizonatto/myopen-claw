"""
memory_db.py — Backend de memória e relacionamentos do OpenClaw (PostgreSQL + pgvector)

Modelo de três camadas:
  contatos                — dados estruturados de pessoas (clientes, família, amigos)
  contato_relacionamentos — grafo de vínculos entre contatos (filho de, sócio de, etc.)
  memories                — observações, eventos, regras e follow-ups

Uma memória pode ser linkada a um contato via contato_id (FK preciso)
ou via entidade TEXT (referência livre a tópicos, empresas, pessoas não cadastradas).

Tipos de memória:
  episodica  — eventos com contexto temporal ("João respondeu em 28/03")
  semantica  — fatos duráveis ("João é diretor de TI na empresa Y")
  procedural — regras aprendidas ("sempre verificar volume > 10k")
  follow_up  — lembretes com data-alvo, opcionalmente recorrentes

Recorrência:
  anual | mensal | semanal — cron em crons/memory_followup_cron.py gera
  follow_ups automáticos N dias antes.

Categorias:
  pessoal      → família, amigos, vida pessoal
  profissional → clientes, parceiros, negócios
  tendencia    → mercado, Twitter, LinkedIn
  concorrente  → monitoramento de concorrentes
  sistema      → regras e aprendizados operacionais do OpenClaw
  conteudo     → ideias de posts, textos, campanhas
"""
from datetime import datetime, timezone, date
from openclaw.db import get_connection, init_extensions, fetchall_dicts

TIPOS_VALIDOS        = {"episodica", "semantica", "procedural", "follow_up"}
RECORRENCIAS_VALIDAS = {None, "anual", "mensal", "semanal"}


# ============================================================================
# Inicialização
# ============================================================================



# ============================================================================
# CONTATOS
# ============================================================================

def add_contato(
    nome: str,
    apelido: str | None = None,
    tipo: str | None = None,
    aniversario: date | None = None,
    telefone: str | None = None,
    whatsapp: str | None = None,
    email: str | None = None,
    linkedin: str | None = None,
    instagram: str | None = None,
    empresa: str | None = None,
    cargo: str | None = None,
    setor: str | None = None,
    notas: str | None = None,
) -> str:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO contatos
                    (nome, apelido, tipo, aniversario, telefone, whatsapp,
                     email, linkedin, instagram, empresa, cargo, setor, notas)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            ''', (nome, apelido, tipo, aniversario, telefone, whatsapp,
                  email, linkedin, instagram, empresa, cargo, setor, notas))
            contato_id = cur.fetchone()["id"]
            conn.commit()
    return str(contato_id)


def update_contato(contato_id: str, **campos) -> None:
    permitidos = {
        "nome", "apelido", "tipo", "aniversario", "telefone", "whatsapp",
        "email", "linkedin", "instagram", "empresa", "cargo", "setor",
        "notas", "ativo", "ultimo_contato",
    }
    campos_validos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos_validos:
        return
    set_clause = ", ".join(f"{k} = %s" for k in campos_validos)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE contatos SET {set_clause}, updated_at = NOW() WHERE id = %s",
                list(campos_validos.values()) + [contato_id],
            )
            conn.commit()


def search_contatos(query: str, limite: int = 10) -> list[dict]:
    like = f"%{query}%"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT * FROM contatos
                WHERE ativo = TRUE
                  AND (nome ILIKE %s OR apelido ILIKE %s OR empresa ILIKE %s)
                ORDER BY nome ASC
                LIMIT %s
            ''', (like, like, like, limite))
            return fetchall_dicts(cur)


def add_relacionamento(
    contato_id: str,
    relacionado_id: str,
    tipo: str,
    notas: str | None = None,
) -> str:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO contato_relacionamentos (contato_id, relacionado_id, tipo, notas)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (contato_id, relacionado_id, tipo) DO NOTHING
                RETURNING id
            ''', (contato_id, relacionado_id, tipo, notas))
            row = cur.fetchone()
            conn.commit()
    return str(row["id"]) if row else ""


def get_contexto_contato(contato_id: str) -> dict:
    """Retorna dados + relacionamentos + memórias + follow-ups em uma única conexão."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM contatos WHERE id = %s", (contato_id,))
            row = cur.fetchone()
            if not row:
                return {}
            contato = dict(row)

            cur.execute('''
                SELECT r.tipo, r.notas, c.id, c.nome, c.apelido, c.tipo AS tipo_contato
                FROM contato_relacionamentos r
                JOIN contatos c ON c.id = r.relacionado_id
                WHERE r.contato_id = %s
            ''', (contato_id,))
            relacionamentos = fetchall_dicts(cur)

            cur.execute('''
                SELECT * FROM memories
                WHERE contato_id = %s
                  AND tipo != 'follow_up'
                  AND (validade IS NULL OR validade > NOW())
                ORDER BY importancia DESC, created_at DESC
                LIMIT 30
            ''', (contato_id,))
            memorias = fetchall_dicts(cur)

            cur.execute('''
                SELECT * FROM memories
                WHERE contato_id = %s
                  AND tipo = 'follow_up'
                  AND (validade IS NULL OR validade > NOW())
                ORDER BY validade ASC NULLS LAST
            ''', (contato_id,))
            follow_ups = fetchall_dicts(cur)

    return {
        "contato":         contato,
        "relacionamentos": relacionamentos,
        "memorias":        memorias,
        "follow_ups":      follow_ups,
    }


def get_aniversarios_proximos(dias: int = 7) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT *,
                    (DATE(NOW()) + (
                        MAKE_DATE(
                            EXTRACT(YEAR FROM NOW())::INT,
                            EXTRACT(MONTH FROM aniversario)::INT,
                            EXTRACT(DAY FROM aniversario)::INT
                        ) - DATE(NOW())
                        + 366
                    ) % 366) AS dias_restantes
                FROM contatos
                WHERE ativo = TRUE
                  AND aniversario IS NOT NULL
                  AND (
                    (MAKE_DATE(
                        EXTRACT(YEAR FROM NOW())::INT,
                        EXTRACT(MONTH FROM aniversario)::INT,
                        EXTRACT(DAY FROM aniversario)::INT
                    ) - DATE(NOW())) BETWEEN 0 AND %s
                    OR
                    (MAKE_DATE(
                        EXTRACT(YEAR FROM NOW())::INT + 1,
                        EXTRACT(MONTH FROM aniversario)::INT,
                        EXTRACT(DAY FROM aniversario)::INT
                    ) - DATE(NOW())) BETWEEN 0 AND %s
                  )
                ORDER BY dias_restantes ASC
            ''', (dias, dias))
            return fetchall_dicts(cur)


# ============================================================================
# MEMORIES
# ============================================================================

def add_memory(
    conteudo: str,
    tipo: str = "semantica",
    categoria: str | None = None,
    contato_id: str | None = None,
    entidade: str | None = None,
    importancia: int = 3,
    validade: datetime | None = None,
    recorrencia: str | None = None,
    dia_mes: int | None = None,
    mes: int | None = None,
    origem: str | None = None,
    embedding: list[float] | None = None,
) -> str:
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {tipo!r}. Use: {TIPOS_VALIDOS}")
    if recorrencia not in RECORRENCIAS_VALIDAS:
        raise ValueError(f"recorrencia inválida: {recorrencia!r}.")
    if recorrencia and (dia_mes is None or mes is None):
        raise ValueError("Memórias recorrentes exigem dia_mes e mes.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO memories
                    (contato_id, entidade, tipo, categoria, conteudo, embedding,
                     importancia, validade, recorrencia, dia_mes, mes, origem)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            ''', (
                contato_id, entidade, tipo, categoria, conteudo, embedding,
                importancia, validade, recorrencia, dia_mes, mes, origem,
            ))
            memory_id = cur.fetchone()["id"]
            conn.commit()
    return str(memory_id)


def get_memory(
    limit: int = 20,
    tipo: str | None = None,
    categoria: str | None = None,
    contato_id: str | None = None,
    entidade: str | None = None,
    apenas_validas: bool = True,
) -> list[dict]:
    filters, params = [], []

    if tipo:
        filters.append("tipo = %s");         params.append(tipo)
    if categoria:
        filters.append("categoria = %s");    params.append(categoria)
    if contato_id:
        filters.append("contato_id = %s");   params.append(contato_id)
    if entidade:
        filters.append("entidade ILIKE %s"); params.append(f"%{entidade}%")
    if apenas_validas:
        filters.append("(validade IS NULL OR validade > NOW())")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT m.*, c.nome AS contato_nome
                FROM memories m
                LEFT JOIN contatos c ON c.id = m.contato_id
                {where}
                ORDER BY importancia DESC, created_at DESC
                LIMIT %s
            ''', params)
            rows = fetchall_dicts(cur)

    _bulk_mark_accessed([r["id"] for r in rows])
    return rows


def get_follow_ups(ate_data: datetime | None = None) -> list[dict]:
    filters = [
        "m.tipo = 'follow_up'",
        "m.recorrencia IS NULL",
        "(m.validade IS NULL OR m.validade > NOW())",
    ]
    params: list = []

    if ate_data:
        filters.append("m.validade <= %s")
        params.append(ate_data)

    where = "WHERE " + " AND ".join(filters)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT m.*, c.nome AS contato_nome
                FROM memories m
                LEFT JOIN contatos c ON c.id = m.contato_id
                {where}
                ORDER BY m.validade ASC NULLS LAST
            ''', params)
            return fetchall_dicts(cur)


def get_upcoming_recurrences(dias_antecedencia: int = 7) -> list[dict]:
    """Retorna memórias recorrentes cuja data cai nos próximos N dias."""
    from datetime import date as _date
    today = _date.today()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT m.*, c.nome AS contato_nome
                FROM memories m
                LEFT JOIN contatos c ON c.id = m.contato_id
                WHERE m.recorrencia IS NOT NULL
                ORDER BY m.mes ASC, m.dia_mes ASC
            ''')
            rows = fetchall_dicts(cur)

    upcoming = []
    for row in rows:
        d, m = row.get("dia_mes"), row.get("mes")
        if not d or not m:
            continue
        try:
            proxima = _date(today.year, m, d)
            if proxima < today:
                proxima = _date(today.year + 1, m, d)
            delta = (proxima - today).days
            if 0 <= delta <= dias_antecedencia:
                row["proxima_ocorrencia"] = proxima
                row["dias_restantes"] = delta
                upcoming.append(row)
        except ValueError:
            continue
    return upcoming


def search_similar(embedding: list[float], limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT m.*, c.nome AS contato_nome,
                       1 - (m.embedding <=> %s::vector) AS similaridade
                FROM memories m
                LEFT JOIN contatos c ON c.id = m.contato_id
                WHERE m.embedding IS NOT NULL
                  AND (m.validade IS NULL OR m.validade > NOW())
                ORDER BY m.embedding <=> %s::vector
                LIMIT %s
            ''', (embedding, embedding, limit))
            return fetchall_dicts(cur)


# ============================================================================
# Utilitários
# ============================================================================

def expire_memory(memory_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE memories SET validade = NOW(), updated_at = NOW() WHERE id = %s",
                (memory_id,)
            )
            conn.commit()


def _bulk_mark_accessed(ids: list) -> None:
    if not ids:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE memories SET acessos = acessos + 1, ultimo_acesso = NOW() WHERE id = ANY(%s)",
                (ids,)
            )
            conn.commit()


