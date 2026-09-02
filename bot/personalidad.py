"""
bot/personalidad.py
--------------------
Lee la personalidad activa de un bot desde la base de datos compartida
(tabla bot_personalities, ver shared/db.py). El bot NUNCA la guarda ni
la edita -- eso lo hace el panel web (panel/personalidad.py). Aqui solo
se lee, para armar el system prompt de la IA en cada respuesta.
"""

from dataclasses import dataclass

from shared.db import BotPersonality, get_session_factory


@dataclass(frozen=True)
class ActivePersonality:
    name: str
    personality: str
    tone: str | None
    language: str | None
    allowed_topics: str | None
    forbidden_topics: str | None


def get_active_personality(bot_slug: str) -> "ActivePersonality | None":
    """
    Devuelve la personalidad guardada para ese bot, o None si todavia no
    se guardo ninguna desde el panel (pantalla /personalidad).
    """
    session = get_session_factory()()
    try:
        row = session.query(BotPersonality).filter_by(bot_slug=bot_slug).first()
        if row is None:
            return None
        return ActivePersonality(
            name=row.name,
            personality=row.personality,
            tone=row.tone,
            language=row.language,
            allowed_topics=row.allowed_topics,
            forbidden_topics=row.forbidden_topics,
        )
    finally:
        session.close()
