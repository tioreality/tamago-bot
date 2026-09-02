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
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class DBConfigError(Exception):
    """Error de configuración de la base de datos: falta alguna variable obligatoria."""


def _build_database_url() -> URL:
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

    try:
        port_int = int(port)
    except ValueError:
        raise DBConfigError("MYSQL_PORT debe ser un número (ej. 3306). Revisa tu archivo .env.")

    # Usamos URL.create de SQLAlchemy en vez de pegar el texto a mano
    # (f"...{password}@{host}..."). Esto es importante: si el usuario o la
    # contraseña de MySQL tienen caracteres especiales como "@", ":" o "/",
    # pegar el texto directo arma una URL inválida y SQLAlchemy confunde
    # dónde termina la contraseña y dónde empieza el host. URL.create
    # escapa esos caracteres automáticamente sin que tengamos que pensar
    # en ello.
    return URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port_int,
        database=database,
        query={"charset": "utf8mb4"},
    )


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


class BotPersonality(Base):
    """
    Personalidad configurable de cada bot. Se edita desde la pantalla
    "/personalidad" del panel web, y el bot la lee de aquí (no de un
    archivo de código) para armar el system prompt que le manda a la
    API de IA en cada respuesta.

    "bot_slug" identifica a qué bot pertenece cada fila (ej. "tamago").
    Se deja preparado desde ya para la Etapa 3, cuando exista un segundo
    bot con personalidad distinta, sin tener que cambiar esta tabla.

    Los campos de canales/permisos/límites de frecuencia (parte de la
    lista completa de "Personalidades de los bots" del proyecto) llegan
    en la siguiente sub-etapa (pantalla de canales y permisos); por ahora
    esta tabla solo cubre identidad y tono, que es lo que edita esta
    pantalla.
    """

    __tablename__ = "bot_personalities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_slug = Column(String(50), nullable=False, unique=True)  # ej: "tamago"
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # El texto completo que se usa como system prompt para la IA.
    personality = Column(Text, nullable=False)

    tone = Column(String(100), nullable=True)  # ej: "cálido y cercano"
    language = Column(String(50), nullable=True)  # ej: "español neutro"

    # Listas simples separadas por comas (una por línea también sirve).
    # Se vuelven listas de verdad en la interfaz del panel; guardarlas
    # como texto plano mantiene esta primera versión simple.
    allowed_topics = Column(Text, nullable=True)
    forbidden_topics = Column(Text, nullable=True)

    presentation_message = Column(Text, nullable=True)

    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
