"""
panel/config.py
----------------
Configuración propia del panel web (además de la de shared/db.py).

Igual que bot/config.py: nada de secretos escritos aquí, todo sale de
variables de entorno. Si falta algo obligatorio, el panel no arranca y
explica exactamente qué falta.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


class PanelConfigError(Exception):
    """Falta una variable de entorno obligatoria para el panel, o tiene un valor inválido."""


@dataclass(frozen=True)
class PanelConfig:
    discord_client_id: str
    discord_client_secret: str
    discord_redirect_uri: str
    discord_bot_token: str  # el mismo DISCORD_TOKEN del bot; se usa para consultar roles
    guild_id: int
    admin_role_id: str
    session_secret: str


def load_panel_config() -> PanelConfig:
    valores = {
        "DISCORD_CLIENT_ID": os.getenv("DISCORD_CLIENT_ID", "").strip(),
        "DISCORD_CLIENT_SECRET": os.getenv("DISCORD_CLIENT_SECRET", "").strip(),
        "DISCORD_REDIRECT_URI": os.getenv("DISCORD_REDIRECT_URI", "").strip(),
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN", "").strip(),
        "GUILD_ID": os.getenv("GUILD_ID", "").strip(),
        "ADMIN_ROLE_ID": os.getenv("ADMIN_ROLE_ID", "").strip(),
        "PANEL_SECRET_KEY": os.getenv("PANEL_SECRET_KEY", "").strip(),
    }

    faltantes = [nombre for nombre, valor in valores.items() if not valor]
    if faltantes:
        raise PanelConfigError(
            "Faltan variables de entorno obligatorias para el panel: "
            + ", ".join(faltantes)
            + ". Revisa tu archivo .env (o las Variables del servicio del panel en Railway). "
            "Ver .env.example para la lista completa con explicación de cada una."
        )

    try:
        guild_id = int(valores["GUILD_ID"])
    except ValueError:
        raise PanelConfigError("GUILD_ID debe ser un número (el ID de tu servidor de Discord).")

    return PanelConfig(
        discord_client_id=valores["DISCORD_CLIENT_ID"],
        discord_client_secret=valores["DISCORD_CLIENT_SECRET"],
        discord_redirect_uri=valores["DISCORD_REDIRECT_URI"],
        discord_bot_token=valores["DISCORD_TOKEN"],
        guild_id=guild_id,
        admin_role_id=valores["ADMIN_ROLE_ID"],
        session_secret=valores["PANEL_SECRET_KEY"],
    )
