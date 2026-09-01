"""
run.py
------
Punto de entrada del proyecto. Ejecuta:

    python run.py

Qué hace, en orden:
1. Carga y valida la configuración desde .env.
2. Configura el sistema de logs.
3. Crea el bot y lo conecta a Discord.

Cómo detener el bot de forma segura:
- Presiona Ctrl+C en la terminal donde se está ejecutando.
  discord.py cierra la conexión de forma ordenada al recibir esa señal.
"""

import sys

import discord

from bot.config import ConfigError, load_config
from bot.logger import setup_logging
from bot.client import build_bot


def main() -> int:
    try:
        config = load_config()
    except ConfigError as e:
        print(f"[ERROR DE CONFIGURACIÓN] {e}")
        return 1

    logger = setup_logging(config.log_level)
    logger.info("Iniciando TAMAGO...")

    bot = build_bot(config)

    try:
        bot.run(config.discord_token, log_handler=None)
    except discord.LoginFailure:
        logger.error(
            "El token de Discord fue rechazado. Verifica DISCORD_TOKEN en tu archivo .env "
            "(y regenera el token en el Developer Portal si sospechas que se filtró)."
        )
        return 1
    except discord.PrivilegedIntentsRequired:
        logger.error(
            "Falta activar un intent privilegiado en el Developer Portal: "
            "Bot > Privileged Gateway Intents > Message Content Intent."
        )
        return 1
    except KeyboardInterrupt:
        logger.info("Detenido manualmente (Ctrl+C). Cierre limpio.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
