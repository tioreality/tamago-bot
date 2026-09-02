"""
panel/auth.py
-------------
Login con Discord (OAuth2) para el panel.

Cómo funciona, en resumen:
1. El usuario hace clic en "Iniciar sesión con Discord" -> lo mandamos a
   Discord con el scope "identify" (solo necesitamos saber quién es).
2. Discord lo regresa a /auth/callback con un "code".
3. Cambiamos ese code por un token de acceso y pedimos "quién eres"
   (/users/@me) a la API de Discord.
4. Con el ID de esa persona, usamos el TOKEN DEL BOT (no el suyo) para
   preguntarle a Discord: "¿esta persona tiene el rol de administrador
   en el servidor TAMAGO?" -> GET /guilds/{guild_id}/members/{user_id}.
5. Si tiene el rol, guardamos su sesión (cookie firmada). Si no, acceso
   denegado.

Nunca pedimos ni guardamos contraseñas: todo el login lo maneja Discord.
"""

import logging
from urllib.parse import urlencode

import httpx

from .config import PanelConfig

logger = logging.getLogger("tamago.panel")

DISCORD_API = "https://discord.com/api/v10"
AUTHORIZE_URL = "https://discord.com/oauth2/authorize"


class AuthError(Exception):
    """Error durante el proceso de login (code inválido, Discord no responde, etc.)."""


def build_avatar_url(discord_user: dict) -> str:
    """
    Arma la URL de la foto de perfil de Discord de esta persona. Si no
    tiene una foto propia, usa el avatar por defecto que Discord le
    asigna a todo el mundo (no hay ningún caso sin foto que mostrar).
    """
    user_id = discord_user.get("id", "")
    avatar_hash = discord_user.get("avatar")

    if avatar_hash:
        extension = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{extension}?size=64"

    # Sin foto propia: avatar por defecto. Discord calcula cuál según si
    # la cuenta ya migró al sistema de nombres nuevo (discriminator "0")
    # o todavia usa el viejo (discriminator de 4 digitos, ej. "#1234").
    discriminator = discord_user.get("discriminator", "0")
    if discriminator and discriminator != "0":
        indice = int(discriminator) % 5
    else:
        indice = (int(user_id) >> 22) % 6 if user_id.isdigit() else 0
    return f"https://cdn.discordapp.com/embed/avatars/{indice}.png"


def build_authorize_url(config: PanelConfig, state: str) -> str:
    params = {
        "client_id": config.discord_client_id,
        "redirect_uri": config.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_user(config: PanelConfig, code: str) -> dict:
    """Cambia el 'code' de la URL por el usuario de Discord que inició sesión."""
    token_data = {
        "client_id": config.discord_client_id,
        "client_secret": config.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.discord_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            logger.warning("Discord OAuth token exchange falló: %s", token_resp.status_code)
            raise AuthError("Discord rechazó el intento de inicio de sesión. Intenta de nuevo.")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise AuthError("Discord no devolvió un token de acceso válido.")

        user_resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise AuthError("No se pudo obtener tu perfil de Discord.")

        return user_resp.json()


async def user_is_admin(config: PanelConfig, user_id: str) -> bool:
    """
    Verifica, usando el token del BOT (no el del usuario), si esta persona
    tiene el rol de administrador configurado (ADMIN_ROLE_ID) en el
    servidor de TAMAGO (GUILD_ID). El usuario nunca ve ni maneja el token
    del bot: esta consulta pasa solo por el backend.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{DISCORD_API}/guilds/{config.guild_id}/members/{user_id}",
            headers={"Authorization": f"Bot {config.discord_bot_token}"},
        )
        if resp.status_code == 404:
            return False  # la persona no está en el servidor
        if resp.status_code != 200:
            logger.error("Error consultando membresía en Discord: %s", resp.status_code)
            raise AuthError("No se pudo verificar tu rol en el servidor. Intenta de nuevo.")

        member = resp.json()
        roles = member.get("roles", [])
        return config.admin_role_id in roles
