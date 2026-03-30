import os
from contextlib import contextmanager
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///shopping_tracker.db")
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    metadata = MetaData(schema="shopping_tracker_mcp")

@contextmanager
def get_session() -> Session:
    """Context manager que fornece uma sessão SQLAlchemy com commit/rollback automático."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

class Compra(Base):
    __tablename__ = "compras"
    __table_args__ = {"schema": "shopping_tracker_mcp"}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    quantidade = Column(Float)
    unidade = Column(String, default="unidade")
    wishlist = Column(Boolean, default=False)
    ultima_compra = Column(Date, nullable=True)
    preco = Column(Float, nullable=True)
    supermercado = Column(String, nullable=True)
    marca = Column(String, nullable=True)
    volume_embalagem = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "quantidade": self.quantidade,
            "unidade": self.unidade,
            "wishlist": self.wishlist,
            "ultima_compra": str(self.ultima_compra) if self.ultima_compra else None,
            "preco": self.preco,
            "loja": self.loja,
            "marca": self.marca,
            "volume_embalagem": self.volume_embalagem
        }

class Wishlist(Base):
    __tablename__ = "wishlist"
    __table_args__ = {"schema": "shopping_tracker_mcp"}
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    quantidade = Column(Float)
    unidade = Column(String, default="unidade")
    wishlist = Column(Boolean, default=True)
    preco = Column(Float, nullable=True)
    loja = Column(String, nullable=True)
    marca = Column(String, nullable=True)
    volume_embalagem = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "quantidade": self.quantidade,
            "unidade": self.unidade,
            "wishlist": self.wishlist,
            "preco": self.preco,
            "loja": self.loja,
            "marca": self.marca,
            "volume_embalagem": self.volume_embalagem
        }
