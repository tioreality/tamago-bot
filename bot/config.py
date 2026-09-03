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

    # Identifica a este bot dentro de la base de datos compartida (tablas
    # bot_personalities, bot_settings, bot_events) y en el panel web
    # (panel/bots_registry.py). Cada uno de los 5 bots tiene su propio
    # .env con su propio BOT_SLUG. Por defecto "tamago" para no romper
    # el despliegue actual si todavía no se agregó esta variable.
    bot_slug: str

    # --- Respuestas con IA (Etapa 2) ---
    anthropic_api_key: str
    anthropic_model: str
    # Nota: los canales autorizados y el interruptor global de IA ya NO
    # viven aquí -- se movieron a la base de datos (tabla bot_settings,
    # ver shared/db.py) para poder editarlos desde el panel web
    # ("Canales" y "Configuración") sin tocar el .env ni redeployar.
    # Ver bot/ajustes.py.
    ai_cooldown_seconds: int
    ai_max_responses_per_minute: int


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


def _get_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        valor = int(raw)
    except ValueError:
        raise ConfigError(f"La variable {name} debe ser un número entero. Valor recibido: {raw!r}")
    if valor <= 0:
        raise ConfigError(f"La variable {name} debe ser mayor que 0. Valor recibido: {raw!r}")
    return valor


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

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_api_key or anthropic_api_key == "tu_api_key_aqui":
        raise ConfigError(
            "Falta ANTHROPIC_API_KEY en el archivo .env (o sigue con el valor de ejemplo). "
            "Es obligatoria a partir de la Etapa 2, para que TAMAGO pueda responder con IA. "
            "Consíguela en: https://console.anthropic.com/settings/keys"
        )

    # El modelo es configurable para no tener que tocar código si Anthropic
    # publica un modelo nuevo o si este deja de estar disponible. Lista
    # actualizada de modelos: https://docs.claude.com/en/docs/about-claude/models
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929").strip()

    ai_cooldown_seconds = _get_positive_int("AI_COOLDOWN_SECONDS", 8)
    ai_max_responses_per_minute = _get_positive_int("AI_MAX_RESPONSES_PER_MINUTE", 10)

    bot_slug = os.getenv("BOT_SLUG", "tamago").strip() or "tamago"

    return Config(
        discord_token=token,
        command_prefix=prefix,
        guild_id=guild_id,
        log_level=log_level,
        bot_slug=bot_slug,
        anthropic_api_key=anthropic_api_key,
        anthropic_model=anthropic_model,
        ai_cooldown_seconds=ai_cooldown_seconds,
        ai_max_responses_per_minute=ai_max_responses_per_minute,
    )
