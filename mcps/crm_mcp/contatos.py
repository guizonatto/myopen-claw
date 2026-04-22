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
    cnpj: str | None = None,
    cnaes: list | None = None,
    notas: str | None = None,
) -> str:
    with get_session() as session:
        contato = Contato(
            nome=nome, apelido=apelido, tipo=tipo, aniversario=aniversario,
            telefone=telefone, whatsapp=whatsapp, email=email,
            linkedin=linkedin, instagram=instagram, empresa=empresa,
            cargo=cargo, setor=setor, cnpj=cnpj, cnaes=cnaes, notas=notas,
        )
        session.add(contato)
        session.flush()
        return str(contato.id)


def update_contato(
    contact_id: str,
    apelido: str | None = None,
    tipo: str | None = None,
    whatsapp: str | None = None,
    email: str | None = None,
    telefone: str | None = None,
    linkedin: str | None = None,
    instagram: str | None = None,
    empresa: str | None = None,
    cargo: str | None = None,
    setor: str | None = None,
    pipeline_status: str | None = None,
    stage: str | None = None,
    icp_type: str | None = None,
    nota: str | None = None,
) -> dict:
    """Atualiza campos de um contato. Notas são appendadas com timestamp, nunca sobrescritas."""
    from datetime import datetime, timezone

    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        VALID_PIPELINE = {"lead", "qualificado", "interesse", "proposta", "fechado", "perdido"}
        if pipeline_status and pipeline_status not in VALID_PIPELINE:
            return {"error": f"pipeline_status inválido. Use: {', '.join(sorted(VALID_PIPELINE))}"}

        updateable = {
            "apelido": apelido, "tipo": tipo, "whatsapp": whatsapp, "email": email,
            "telefone": telefone, "linkedin": linkedin, "instagram": instagram,
            "empresa": empresa, "cargo": cargo, "setor": setor,
            "pipeline_status": pipeline_status, "stage": stage, "icp_type": icp_type,
        }
        for field, value in updateable.items():
            if value is not None:
                setattr(contato, field, value)

        if nota:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            existing = contato.notas or ""
            contato.notas = f"{existing}\n{ts}: {nota}".strip()

        contato.ultimo_contato = datetime.now(timezone.utc)
        contato.updated_at = datetime.now(timezone.utc)
        session.flush()
        return contato.to_dict()


def list_contacts_to_follow_up(hours_since_last_contact: int = 24, limit: int = 10) -> list[dict]:
    """Retorna contatos elegíveis para abordagem proativa:
    - pipeline_status não é 'fechado' nem 'perdido'
    - ultimo_contato é NULL ou mais antigo que hours_since_last_contact
    - Ordem: nunca contactados primeiro, depois os mais antigos
    """
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_since_last_contact)

    with get_session() as session:
        results = (
            session.query(Contato)
            .filter(
                Contato.ativo == True,  # noqa: E712
                or_(
                    Contato.pipeline_status == None,  # noqa: E711
                    ~Contato.pipeline_status.in_(["fechado", "perdido"]),
                ),
                or_(
                    Contato.ultimo_contato == None,  # noqa: E711
                    Contato.ultimo_contato < cutoff,
                ),
            )
            .order_by(Contato.ultimo_contato.asc().nullsfirst())
            .limit(limit)
            .all()
        )
        return [c.to_dict() for c in results]


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
                    Contato.email.ilike(like),
                    Contato.telefone.ilike(like),
                    Contato.whatsapp.ilike(like),
                    Contato.linkedin.ilike(like),
                    Contato.instagram.ilike(like),
                ),
            )
            .order_by(Contato.nome.asc())
            .limit(limite)
            .all()
        )
        return [c.to_dict() for c in results]
