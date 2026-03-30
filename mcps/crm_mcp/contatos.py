from datetime import date
from sqlalchemy import or_
from db import get_session
from models import Contato


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
    with get_session() as session:
        contato = Contato(
            nome=nome, apelido=apelido, tipo=tipo, aniversario=aniversario,
            telefone=telefone, whatsapp=whatsapp, email=email,
            linkedin=linkedin, instagram=instagram, empresa=empresa,
            cargo=cargo, setor=setor, notas=notas,
        )
        session.add(contato)
        session.flush()
        return str(contato.id)


def search_contatos(query: str, limite: int = 10) -> list[dict]:
    like = f"%{query}%"
    with get_session() as session:
        results = (
            session.query(Contato)
            .filter(
                Contato.ativo == True,  # noqa: E712
                or_(
                    Contato.nome.ilike(like),
                    Contato.apelido.ilike(like),
                    Contato.empresa.ilike(like),
                ),
            )
            .order_by(Contato.nome.asc())
            .limit(limite)
            .all()
        )
        return [c.to_dict() for c in results]
