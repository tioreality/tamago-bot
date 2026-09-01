"""
config.py
---------
Carga y valida la configuración del bot a partir de variables de entorno
(archivo .env). Ningún secreto se escribe aquí en el código: todo viene
del archivo .env, que nunca se sube al repositorio.

Si falta una variable obligatoria, el programa se detiene con un mensaje
claro en lugar de fallar de forma confusa más adelante.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env al entorno del proceso.
load_dotenv()


class ConfigError(Exception):
    """Error de configuración: falta una variable obligatoria o tiene un valor inválido."""


@dataclass(frozen=True)
class Config:
    discord_token: str
    command_prefix: str
    guild_id: int | None
    log_level: str


def _get_optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(
            f"La variable {name} debe ser un número entero (ID de Discord). "
            f"Valor recibido: {raw!r}"
        )


def load_config() -> Config:
    """Lee y valida las variables de entorno. Lanza ConfigError si algo falta o es inválido."""

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "tu_token_aqui":
        raise ConfigError(
            "Falta DISCORD_TOKEN en el archivo .env (o sigue con el valor de ejemplo). "
            "Copia .env.example como .env y pega el token real de tu bot "
            "(Discord Developer Portal > tu aplicación > Bot > Reset Token)."
        )

    prefix = os.getenv("COMMAND_PREFIX", "!").strip() or "!"

    guild_id = _get_optional_int("GUILD_ID")

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
    if log_level not in valid_levels:
        raise ConfigError(
            f"LOG_LEVEL={log_level!r} no es válido. Usa uno de: {', '.join(sorted(valid_levels))}."
        )

    return Config(
        discord_token=token,
        command_prefix=prefix,
        guild_id=guild_id,
        log_level=log_level,
    )
