"""
bot/ajustes.py
---------------
Lee (y, para el interruptor de IA, tambien escribe) los ajustes
globales de un bot desde la base de datos compartida (tabla
bot_settings, ver shared/db.py):
- Si las respuestas de IA estan activadas o no.
- En que canales de Discord puede responder con IA.

Antes esto vivia en una variable de entorno (AI_ALLOWED_CHANNEL_IDS) y
en memoria del proceso (el interruptor "!ia on/off" se perdia al
reiniciar el bot). Ahora vive en la base de datos: se puede cambiar
desde el panel web (pantallas "Canales" y "Configuracion") sin tocar
el .env ni reiniciar nada, el interruptor sobrevive a un reinicio del
bot, y el comando "!ia on/off" de Discord queda sincronizado con el
panel porque los dos leen y escriben la misma fila.
"""

from dataclasses import dataclass

from shared.db import BotSettings, get_session_factory


@dataclass(frozen=True)
class ActiveSettings:
    ai_enabled: bool
    allowed_channel_ids: frozenset[int]


def _parse_channel_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    ids = set()
    for pedazo in raw.replace(",", "\n").splitlines():
        pedazo = pedazo.strip()
        if pedazo.isdigit():
            ids.add(int(pedazo))
    return frozenset(ids)


def get_active_settings(bot_slug: str) -> ActiveSettings:
    """
    Devuelve los ajustes actuales para ese bot. Si todavia no hay
    ninguna fila guardada (nadie configuro nada desde el panel
    todavia), usa los valores por defecto mas seguros: IA activada,
    pero CERO canales autorizados -- asi el bot no responde con IA en
    ningun lado hasta que un administrador marque al menos un canal
    desde la pantalla "Canales" del panel.
    """
    session = get_session_factory()()
    try:
        row = session.query(BotSettings).filter_by(bot_slug=bot_slug).first()
        if row is None:
            return ActiveSettings(ai_enabled=True, allowed_channel_ids=frozenset())
        return ActiveSettings(
            ai_enabled=row.ai_enabled,
            allowed_channel_ids=_parse_channel_ids(row.allowed_channel_ids),
        )
    finally:
        session.close()


def set_ai_enabled(bot_slug: str, value: bool) -> None:
    """
    Prende o apaga las respuestas de IA para ese bot. Lo usa el comando
    "!ia on/off" de Discord (ver bot/client.py); la pantalla
    "Configuracion" del panel web usa su propia función equivalente
    (panel/ajustes.py) sobre la misma fila.
    """
    session = get_session_factory()()
    try:
        row = session.query(BotSettings).filter_by(bot_slug=bot_slug).first()
        if row is None:
            row = BotSettings(bot_slug=bot_slug, ai_enabled=value, allowed_channel_ids="")
            session.add(row)
        else:
            row.ai_enabled = value
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def set_avatar_url(bot_slug: str, avatar_url: str) -> None:
    """
    Guarda la URL de la foto de perfil de este bot en Discord, para que
    el panel web la muestre en vez de un emoji generico. Se llama una
    vez cada vez que el bot se conecta (bot/client.py, evento
    on_ready) -- asi el panel siempre tiene la foto mas reciente, sin
    que un administrador tenga que subirla a mano.
    """
    session = get_session_factory()()
    try:
        row = session.query(BotSettings).filter_by(bot_slug=bot_slug).first()
        if row is None:
            row = BotSettings(
                bot_slug=bot_slug, ai_enabled=True, allowed_channel_ids="", avatar_url=avatar_url
            )
            session.add(row)
        else:
            row.avatar_url = avatar_url
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
