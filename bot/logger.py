"""
logger.py
---------
Configura el sistema de registros (logs) del bot.

Qué se guarda: eventos técnicos (inicio, conexión, comandos ejecutados,
errores) con fecha y hora. NO se guardan tokens, claves ni contenido
privado de mensajes.

Dónde se guarda: en la carpeta logs/, en un archivo que rota
automáticamente para no crecer sin límite.

Cómo borrarlo: puedes borrar el contenido de la carpeta logs/ en
cualquier momento con el bot detenido; se volverá a crear solo.
"""

import logging
import logging.handlers
import os

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def setup_logging(log_level: str = "INFO", bot_slug: str = "tamago") -> logging.Logger:
    """
    "bot_slug" identifica a que bot pertenecen estos logs (ej. "tamago",
    "aji"...). Se usa para el nombre del logger y del archivo, para que
    cuando este mismo codigo corra para otro bot (Railway, otro .env),
    sus logs no se mezclen con los de TAMAGO ni se llamen "tamago.log"
    por error.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{bot_slug}.log")

    logger = logging.getLogger(bot_slug)
    logger.setLevel(log_level)
    logger.handlers.clear()  # evita duplicar handlers si setup_logging se llama más de una vez

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Consola: para ver qué pasa mientras desarrollas.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Archivo con rotación: máximo 5 archivos de 1 MB cada uno.
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Silenciamos el ruido interno de discord.py salvo advertencias/errores.
    logging.getLogger("discord").setLevel(logging.WARNING)

    return logger
