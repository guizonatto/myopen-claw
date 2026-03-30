import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL não definida")
        _engine = create_engine(dsn, pool_size=5, max_overflow=5, pool_pre_ping=True)
        logger.info("SQLAlchemy engine criado")
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine())
    return _SessionLocal


@contextmanager
def get_session() -> Session:
    """Context manager que fornece uma sessão SQLAlchemy com commit/rollback automático."""
    Session = _get_session_factory()
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
