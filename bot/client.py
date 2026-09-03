"""
client.py
---------
Define la clase TamagoBot: la instancia del bot de Discord.

Etapa 1 (MVP): conexión con Discord y comando "!ping" de prueba.

Etapa 2 (en curso): TAMAGO ahora responde con IA cuando lo mencionan
directamente (@TAMAGO) en un canal autorizado, usando la personalidad
guardada desde el panel web (bot/personalidad.py + bot/ai.py), con
controles anti-spam (bot/antispam.py): cooldown, límite por minuto,
lista de canales autorizados, mensajes repetidos, e interruptor global
("!ia on" / "!ia off" / "!ia estado", solo para Administradores). Los
canales autorizados y el interruptor viven en la base de datos
(bot/ajustes.py), compartidos con las pantallas "Canales" y
"Configuración" del panel web.

Todavía NO incluye (llegará en etapas posteriores, según el plan del
proyecto):
- Comandos slash.
- Conversaciones entre bots (Etapa 3).
- Moderación avanzada y memoria persistente (Etapa 4).
"""

import asyncio
import logging

import discord
from discord.ext import commands

from . import antispam
from .ai import generate_response
from .ajustes import get_active_settings, set_ai_enabled, set_avatar_url
from .config import Config
from .personalidad import get_active_personality
from shared.db import BotEvent, session_scope


def _log_blocked_event(config: Config, message: discord.Message, reason: str) -> None:
    """Guarda en la base de datos por qué se bloqueó una respuesta de IA."""
    try:
        with session_scope() as session:
            session.add(
                BotEvent(
                    bot_slug=config.bot_slug,
                    event_type="bloqueo",
                    description=f"Respuesta de IA bloqueada: {reason}",
                    guild_id=str(message.guild.id) if message.guild else None,
                    channel_id=str(message.channel.id),
                    user_id=str(message.author.id),
                )
            )
    except Exception as e:  # la base de datos puede fallar sin tumbar al bot
        logging.getLogger(config.bot_slug).warning("No se pudo guardar el registro de bloqueo: %s", e)


async def _handle_ai_mention(bot: commands.Bot, config: Config, message: discord.Message) -> None:
    logger = logging.getLogger(config.bot_slug)

    content = message.content
    for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
        content = content.replace(mention, "")
    content = content.strip()

    if not content:
        content = "(el usuario solo te mencionó, sin escribir nada más -- salúdalo)"

    if len(content) > 800:
        await message.channel.send(
            f"🐣 ¡Uy, {message.author.mention}! Ese mensaje es bastante largo para mí, "
            "¿me lo resumes un poco?"
        )
        return

    # Los ajustes (interruptor + canales autorizados) viven en la base de
    # datos -- se leen en cada mención para reflejar casi al instante
    # cualquier cambio hecho desde el panel web o el comando "!ia".
    settings = await asyncio.to_thread(get_active_settings, config.bot_slug)

    reason = antispam.check_message(
        channel_id=message.channel.id,
        user_id=message.author.id,
        content=content,
        enabled=settings.ai_enabled,
        allowed_channel_ids=settings.allowed_channel_ids,
        cooldown_seconds=config.ai_cooldown_seconds,
        max_responses_per_minute=config.ai_max_responses_per_minute,
    )
    if reason is not None:
        logger.info(
            "Respuesta de IA bloqueada (%s) -- canal=%s usuario=%s",
            reason, message.channel.id, message.author.id,
        )
        await asyncio.to_thread(_log_blocked_event, config, message, reason)
        return

    # Las consultas a la base de datos son bloqueantes (no async): las
    # corremos en un hilo aparte para no congelar al bot mientras esperan.
    personality = await asyncio.to_thread(get_active_personality, config.bot_slug)
    if personality is None:
        logger.warning("Todavía no hay personalidad guardada para '%s' en la base de datos.", config.bot_slug)
        return

    async with message.channel.typing():
        try:
            reply = await generate_response(config, personality, content)
        except Exception as e:
            logger.error("Error llamando a la API de Claude: %s", e)
            await message.channel.send(
                f"🐣 Se me enredó el hilo un segundo, {message.author.mention}... "
                "¿me preguntas de nuevo en un ratito?"
            )
            return

    antispam.register_response(channel_id=message.channel.id, user_id=message.author.id, content=content)
    # Igual que en "!ping" más abajo: usamos bot.user.name (el nombre real
    # de la cuenta de Discord) en vez de "TAMAGO" a mano, porque este mismo
    # código corre para cada bot (AJI, SABA, POTATO...) con su propio nombre.
    logger.info("%s respondió con IA a %s en #%s", bot.user.name, message.author, message.channel)
    await message.channel.send(reply)


def build_bot(config: Config) -> commands.Bot:
    # Intents = qué tipo de eventos puede "ver" el bot.
    # message_content es un intent privilegiado: hay que activarlo también
    # en el Discord Developer Portal (Bot > Privileged Gateway Intents),
    # si no, el bot no podrá leer el texto de los mensajes para detectar
    # comandos ni menciones.
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix=config.command_prefix, intents=intents)
    logger = logging.getLogger(config.bot_slug)

    @bot.event
    async def on_ready():
        logger.info("Conectado como %s (ID: %s)", bot.user, bot.user.id)
        logger.info("Prefijo de comandos activo: %s", config.command_prefix)
        # Guarda la foto de perfil real de este bot en la base de datos
        # compartida, para que el panel web la muestre en vez de un
        # emoji generico. Si falla (ej. la base de datos no responde en
        # ese momento), no tumba al bot -- el panel simplemente sigue
        # mostrando el emoji hasta el proximo reinicio.
        try:
            await asyncio.to_thread(set_avatar_url, config.bot_slug, str(bot.user.display_avatar.url))
        except Exception as e:
            logger.warning("No se pudo guardar la foto de perfil en la base de datos: %s", e)
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
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("🚫 Ese comando es solo para Administradores del servidor.")
            return
        logger.error("Error ejecutando un comando: %s", error)
        await ctx.send("⚠️ Ocurrió un error al procesar ese comando. Ya quedó registrado.")

    @bot.event
    async def on_message(message: discord.Message):
        # Nunca respondemos a otros bots (ni a nosotros mismos): evita
        # bucles y respuestas en cadena entre bots del servidor.
        if message.author.bot:
            return

        # Deja que los comandos con prefijo (ej. "!ping") sigan funcionando
        # exactamente igual que antes.
        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.invoke(ctx)
            return

        # Solo respondemos con IA si mencionan directamente a este bot.
        if bot.user in message.mentions:
            await _handle_ai_mention(bot, config, message)

    @bot.command(name="ping")
    async def ping(ctx: commands.Context):
        """Comando de prueba: confirma que este bot está vivo y respondiendo."""
        logger.info("Comando !ping usado por %s en #%s", ctx.author, ctx.channel)
        # Usamos el nombre real de la cuenta de Discord (bot.user.name) en
        # vez de "TAMAGO" a mano: con varios bots corriendo este mismo
        # código, cada uno debe presentarse con su propio nombre.
        await ctx.send(f"🏓 Pong! Soy {bot.user.name} y estoy en línea, {ctx.author.mention}.")

    @bot.command(name="ia")
    @commands.has_permissions(administrator=True)
    async def ia_toggle(ctx: commands.Context, accion: str = "estado"):
        """Enciende/apaga/consulta las respuestas de IA. Solo Administradores.

        Guarda el valor en la base de datos (tabla bot_settings), no en
        memoria: sobrevive a un reinicio del bot y queda sincronizado con
        la pantalla "Configuración" del panel web.
        """
        accion = accion.lower().strip()
        if accion in ("on", "encender", "activar"):
            await asyncio.to_thread(set_ai_enabled, config.bot_slug, True)
            logger.info("IA activada por %s", ctx.author)
            await ctx.send("🐣 Listo, ya puedo responder con IA de nuevo.")
        elif accion in ("off", "apagar", "desactivar"):
            await asyncio.to_thread(set_ai_enabled, config.bot_slug, False)
            logger.info("IA desactivada por %s", ctx.author)
            await ctx.send("🐣 Ok, dejo de responder con IA hasta que me vuelvan a encender.")
        elif accion in ("estado", "status"):
            settings = await asyncio.to_thread(get_active_settings, config.bot_slug)
            estado = "activada ✅" if settings.ai_enabled else "desactivada ⛔"
            await ctx.send(f"🐣 Mi IA está {estado} ahora mismo.")
        else:
            await ctx.send("Uso: `!ia on`, `!ia off` o `!ia estado`.")

    return bot
