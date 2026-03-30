from datetime import datetime, timezone
from sqlalchemy import or_
from db import get_session
from models import Memory

TIPOS_VALIDOS = {"episodica", "semantica", "procedural", "follow_up"}
RECORRENCIAS_VALIDAS = {None, "anual", "mensal", "semanal"}


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

    with get_session() as session:
        memory = Memory(
            contato_id=contato_id,
            entidade=entidade,
            tipo=tipo,
            categoria=categoria,
            conteudo=conteudo,
            embedding=embedding,
            importancia=importancia,
            validade=validade,
            recorrencia=recorrencia,
            dia_mes=dia_mes,
            mes=mes,
            origem=origem,
        )
        session.add(memory)
        session.flush()
        return str(memory.id)


def get_memory(
    limit: int = 20,
    tipo: str | None = None,
    categoria: str | None = None,
    contato_id: str | None = None,
    entidade: str | None = None,
    apenas_validas: bool = True,
) -> list[dict]:
    now = datetime.now(tz=timezone.utc)
    with get_session() as session:
        q = session.query(Memory)

        if tipo:
            q = q.filter(Memory.tipo == tipo)
        if categoria:
            q = q.filter(Memory.categoria == categoria)
        if contato_id:
            q = q.filter(Memory.contato_id == contato_id)
        if entidade:
            q = q.filter(Memory.entidade.ilike(f"%{entidade}%"))
        if apenas_validas:
            q = q.filter(or_(Memory.validade == None, Memory.validade > now))  # noqa: E711

        results = (
            q.order_by(Memory.importancia.desc(), Memory.created_at.desc())
            .limit(limit)
            .all()
        )
        return [m.to_dict() for m in results]
