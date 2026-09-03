"""
panel/ajustes.py
------------------
Lógica de las pantallas "Canales" y "Configuración" del panel:

- Canales: en qué canales de Discord puede responder TAMAGO con IA.
- Configuración: interruptor global de IA (encendida/apagada).

Ambas pantallas leen y escriben la misma tabla (bot_settings, ver
shared/db.py). El bot la lee en cada mensaje, así que un cambio
guardado aquí se refleja casi al instante, sin reiniciar nada -- igual
que la personalidad.
"""

import logging
from dataclasses import dataclass

import httpx

from .config import PanelConfig
from shared.db import BotSettings, get_session_factory

logger = logging.getLogger("tamago.panel")

DISCORD_API = "https://discord.com/api/v10"

# Tipos de canal de Discord donde tiene sentido que TAMAGO responda con
# texto: 0 = canal de texto normal, 5 = canal de anuncios. Se omiten
# categorías, canales de voz, foros, etc.
_TIPOS_CANAL_TEXTO = {0, 5}


@dataclass
class SettingsData:
    ai_enabled: bool
    allowed_channel_ids: list[str]


def _parse_channel_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    vistos: set[str] = set()
    ids: list[str] = []
    for linea in raw.replace(",", "\n").splitlines():
        pedazo = linea.strip()
        if pedazo and pedazo not in vistos:
            vistos.add(pedazo)
            ids.append(pedazo)
    return ids


def get_settings(bot_slug: str) -> SettingsData:
    """
    Devuelve los ajustes guardados para ese bot. Si todavía no existe
    ninguna fila (primera vez que se abren estas pantallas), devuelve
    los valores por defecto más seguros: IA activada, pero sin ningún
    canal autorizado -- no se guarda nada hasta que alguien le dé
    "Guardar" desde el panel.
    """
    session = get_session_factory()()
    try:
        row = session.query(BotSettings).filter_by(bot_slug=bot_slug).first()
        if row is None:
            return SettingsData(ai_enabled=True, allowed_channel_ids=[])
        return SettingsData(
            ai_enabled=row.ai_enabled,
            allowed_channel_ids=_parse_channel_ids(row.allowed_channel_ids),
        )
    finally:
        session.close()


def _get_or_create(session, bot_slug: str) -> BotSettings:
    row = session.query(BotSettings).filter_by(bot_slug=bot_slug).first()
    if row is None:
        row = BotSettings(bot_slug=bot_slug, ai_enabled=True, allowed_channel_ids="")
        session.add(row)
    return row


def save_ai_enabled(bot_slug: str, value: bool) -> None:
    """Prende o apaga las respuestas de IA. Usado por la pantalla 'Configuración'."""
    session = get_session_factory()()
    try:
        row = _get_or_create(session, bot_slug)
        row.ai_enabled = value
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_allowed_channels(bot_slug: str, channel_ids: list[str]) -> None:
    """Reemplaza la lista completa de canales autorizados. Usado por 'Canales'."""
    session = get_session_factory()()
    try:
        row = _get_or_create(session, bot_slug)
        row.allowed_channel_ids = "\n".join(channel_ids)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_avatar_urls(bot_slugs: list[str]) -> dict[str, str]:
    """
    Devuelve {slug: avatar_url} para los bots pedidos, en UNA sola
    consulta (evita una consulta por bot al armar la barra lateral,
    que se pinta en cada pantalla). El bot mismo guarda su avatar_url
    al conectarse a Discord (ver bot/client.py); si un bot todavia no
    se ha conectado ni una vez, no aparece en el resultado -- el panel
    cae al emoji de respaldo en ese caso.
    """
    if not bot_slugs:
        return {}
    session = get_session_factory()()
    try:
        filas = (
            session.query(BotSettings.bot_slug, BotSettings.avatar_url)
            .filter(BotSettings.bot_slug.in_(bot_slugs))
            .all()
        )
        return {slug: avatar_url for slug, avatar_url in filas if avatar_url}
    finally:
        session.close()


async def fetch_guild_text_channels(config: PanelConfig) -> list[dict]:
    """
    Pide a la API de Discord (con el token del bot, igual que auth.py
    para verificar roles) la lista de canales de texto del servidor,
    para mostrar nombres reales en vez de solo IDs en la pantalla
    "Canales". Si Discord no responde por cualquier motivo, devuelve
    una lista vacía -- la pantalla sigue funcionando, solo cae al modo
    manual (escribir los IDs a mano).
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{DISCORD_API}/guilds/{config.guild_id}/channels",
                headers={"Authorization": f"Bot {config.discord_bot_token}"},
            )
    except httpx.HTTPError as e:
        logger.warning("Error de red obteniendo la lista de canales de Discord: %s", e)
        return []

    if resp.status_code != 200:
        logger.warning("No se pudo obtener la lista de canales de Discord: %s", resp.status_code)
        return []

    canales = resp.json()
    disponibles = [
        {"id": str(c["id"]), "nombre": c.get("name") or c["id"]}
        for c in canales
        if c.get("type") in _TIPOS_CANAL_TEXTO
    ]
    return sorted(disponibles, key=lambda c: c["nombre"].lower())
