"""
client.py
---------
Define la clase TamagoBot: la instancia del bot de Discord.

Etapa 1 (MVP): el bot solo hace lo mínimo para demostrar que funciona:
- Se conecta a Discord con un token oficial de bot.
- Responde a un comando de texto "!ping" (o el prefijo que configures).
- Registra en los logs cuándo se conecta y qué comandos ejecuta.

Todavía NO incluye (llegará en etapas posteriores, según el plan del
proyecto):
- Comandos slash (Etapa 2).
- Personalidad configurable y respuestas con IA (Etapa 2).
- Conversaciones entre bots (Etapa 3).
- Moderación avanzada y memoria persistente (Etapa 4).
"""

import logging

import discord
from discord.ext import commands

from .config import Config


def build_bot(config: Config) -> commands.Bot:
    # Intents = qué tipo de eventos puede "ver" el bot.
    # message_content es un intent privilegiado: hay que activarlo también
    # en el Discord Developer Portal (Bot > Privileged Gateway Intents),
    # si no, el bot no podrá leer el texto de los mensajes para detectar
    # comandos ni menciones.
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix=config.command_prefix, intents=intents)
    logger = logging.getLogger("tamago")

    @bot.event
    async def on_ready():
        logger.info("Conectado como %s (ID: %s)", bot.user, bot.user.id)
        logger.info("Prefijo de comandos activo: %s", config.command_prefix)
        if config.guild_id:
            guild = bot.get_guild(config.guild_id)
            if guild:
                logger.info("Servidor objetivo encontrado: %s", guild.name)
            else:
                logger.warning(
                    "GUILD_ID configurado (%s) pero el bot no está en ese servidor.",
                    config.guild_id,
                )

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        # Evita que errores comunes (comando inexistente, etc.) tumben el bot
        # o expongan detalles internos en el chat.
        if isinstance(error, commands.CommandNotFound):
            return  # ignoramos silenciosamente comandos que no existen
        logger.error("Error ejecutando un comando: %s", error)
        await ctx.send("⚠️ Ocurrió un error al procesar ese comando. Ya quedó registrado.")

    @bot.command(name="ping")
    async def ping(ctx: commands.Context):
        """Comando de prueba: confirma que TAMAGO está vivo y respondiendo."""
        logger.info("Comando !ping usado por %s en #%s", ctx.author, ctx.channel)
        await ctx.send(f"🏓 Pong! Soy TAMAGO y estoy en línea, {ctx.author.mention}.")

    return bot
