"""
panel/bots_registry.py
-----------------------
Lista fija de los bots que administra este panel.

Se eligió una lista simple en código (en vez de una tabla en la base de
datos con su propia pantalla) porque son pocos bots (hasta 5) y cambian
rara vez: agregar uno nuevo es agregar una línea aquí y volver a
desplegar el panel en Railway -- no hace falta tocar la base de datos.
Las tablas "bot_personalities" y "bot_settings" (shared/db.py) ya tenían
la columna "bot_slug" preparada desde el principio justo para este
momento, así que no hace falta ninguna migración para agregar un bot
nuevo, solo para la tabla de logs (ver scripts/migrate_add_bot_slug_to_bot_events.py).

Reglas para el "slug":
- Corto, en minúsculas, sin espacios ni tildes ni símbolos raros
  (se usa en la URL del panel, ej. /bots/tamago/personalidad).
- Debe coincidir EXACTO con la variable BOT_SLUG en el archivo .env del
  bot correspondiente (ver bot/config.py) -- así el bot lee/escribe la
  fila correcta en la base de datos compartida.
- Una vez que un bot ya tiene datos guardados (personalidad, canales),
  no le cambies el slug: perdería el vínculo con esos datos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BotInfo:
    slug: str
    name: str
    emoji: str = "🤖"


# Para agregar un bot nuevo:
#   1. Crea su aplicación en el Discord Developer Portal (token propio).
#   2. Agrégalo aquí abajo, con un slug nuevo que no se repita.
#   3. En su propio repositorio/servicio de Railway, pon en el .env:
#        DISCORD_TOKEN=<el token de ESE bot>
#        BOT_SLUG=<el mismo slug que pusiste aquí>
#        (el resto de variables -- base de datos, GUILD_ID, etc. -- son
#        las mismas para los 5 bots, porque comparten servidor y base
#        de datos).
#   4. Vuelve a desplegar el panel (este servicio) para que aparezca en
#      la lista. Entra al panel y configúrale su personalidad.
BOTS: list[BotInfo] = [
    BotInfo(slug="tamago", name="TAMAGO", emoji="🐣"),
    BotInfo(slug="aji", name="AJI", emoji="🐟"),
    BotInfo(slug="salmon", name="SALMON", emoji="🍣"),
    BotInfo(slug="saba", name="SABA", emoji="🐠"),
    BotInfo(slug="potato", name="POTATO", emoji="🥔"),
]

_BY_SLUG = {b.slug: b for b in BOTS}


def get_bot(slug: str) -> BotInfo | None:
    """Devuelve la info del bot con ese slug, o None si no está registrado."""
    return _BY_SLUG.get(slug)
