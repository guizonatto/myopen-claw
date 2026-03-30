import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy import MetaData
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    metadata = MetaData(schema="crm_mcp")


class Contato(Base):
    __tablename__ = 'contatos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    nome = Column(Text, nullable=False)
    apelido = Column(Text, nullable=True)
    tipo = Column(Text, nullable=True)
    aniversario = Column(DateTime, nullable=True)
    telefone = Column(Text, nullable=True)
    whatsapp = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    linkedin = Column(Text, nullable=True)
    instagram = Column(Text, nullable=True)
    empresa = Column(Text, nullable=True)
    cargo = Column(Text, nullable=True)
    setor = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)
    ativo = Column(Boolean, server_default='true')
    ultimo_contato = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(Vector(1536), nullable=True)

    def to_dict(self) -> dict:
        result = {}
        for c in self.__table__.columns:
            val = getattr(self, c.name)
            if isinstance(val, uuid.UUID):
                val = str(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            result[c.name] = val
        return result



class ContatoRelacionamento(Base):
    __tablename__ = 'contato_relacionamentos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    relacionado_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    tipo = Column(Text, nullable=False)
    notas = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        result = {}
        for c in self.__table__.columns:
            val = getattr(self, c.name)
            if isinstance(val, uuid.UUID):
                val = str(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            result[c.name] = val
        return result
