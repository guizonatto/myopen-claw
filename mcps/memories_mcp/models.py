import uuid
from datetime import datetime
from sqlalchemy import Column, Text, SmallInteger, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy import MetaData
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    metadata = MetaData(schema="memories_mcp")


class Memory(Base):
    __tablename__ = 'memories'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), nullable=True)
    entidade = Column(Text, nullable=True)
    tipo = Column(Text, nullable=False, server_default='semantica')
    categoria = Column(Text, nullable=True)
    conteudo = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    importancia = Column(SmallInteger, server_default='3')
    validade = Column(DateTime(timezone=True), nullable=True)
    recorrencia = Column(Text, nullable=True)
    dia_mes = Column(SmallInteger, nullable=True)
    mes = Column(SmallInteger, nullable=True)
    acessos = Column(Integer, server_default='0')
    ultimo_acesso = Column(DateTime(timezone=True), nullable=True)
    origem = Column(Text, nullable=True)

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
