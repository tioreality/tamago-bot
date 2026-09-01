"""
shared/db.py
------------
Conexión a la base de datos MySQL compartida entre el bot y el panel.

Ambos servicios (bot y panel) se conectan a la MISMA base de datos, cada
uno leyendo las mismas variables de entorno (MYSQL_HOST, MYSQL_PORT,
MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE). Así, un cambio guardado
desde el panel lo puede leer el bot casi al instante, sin reiniciar nada.

Ningún secreto vive en este archivo: todo viene de variables de entorno.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class DBConfigError(Exception):
    """Error de configuración de la base de datos: falta alguna variable obligatoria."""


def _build_database_url() -> str:
    host = os.getenv("MYSQL_HOST", "").strip()
    port = os.getenv("MYSQL_PORT", "3306").strip()
    user = os.getenv("MYSQL_USER", "").strip()
    password = os.getenv("MYSQL_PASSWORD", "").strip()
    database = os.getenv("MYSQL_DATABASE", "").strip()

    faltantes = [
        nombre
        for nombre, valor in [
            ("MYSQL_HOST", host),
            ("MYSQL_USER", user),
            ("MYSQL_PASSWORD", password),
            ("MYSQL_DATABASE", database),
        ]
        if not valor
    ]
    if faltantes:
        raise DBConfigError(
            "Faltan variables de entorno para conectar a la base de datos: "
            + ", ".join(faltantes)
            + ". Revisa tu archivo .env (o las Variables del servicio en Railway)."
        )

    # pymysql como driver; los valores se escapan automáticamente (nunca se
    # arma la URL con texto pegado a mano en otras partes del código).
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_build_database_url(), pool_pre_ping=True, pool_recycle=280)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


@contextmanager
def session_scope():
    """Uso: with session_scope() as session: ... (hace commit/rollback solo)."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Crea las tablas que todavía no existan. Seguro de correr varias veces."""
    Base.metadata.create_all(get_engine())


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class BotEvent(Base):
    """
    Registro de actividad para la pantalla de "logs" del panel.
    Es un complemento visual a logs/tamago.log, no un reemplazo: el archivo
    sigue existiendo para depuración técnica local.
    """

    __tablename__ = "bot_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    event_type = Column(String(50), nullable=False)  # ej: "comando", "bloqueo", "error"
    description = Column(Text, nullable=False)
    guild_id = Column(String(32), nullable=True)
    channel_id = Column(String(32), nullable=True)
    user_id = Column(String(32), nullable=True)
