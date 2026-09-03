"""
scripts/list_roles.py
----------------------
Script de diagnóstico (no forma parte del panel ni del bot): lista todos
los roles del servidor de Discord configurado en GUILD_ID, con su ID real,
para que puedas copiar y pegar el correcto en ADMIN_ROLE_ID sin tener que
ir a cazarlo a mano en Discord.

Marca con "<-- posible rol de administrador" cualquier rol cuyo nombre se
parezca a "admin", "administrador", "staff" o "moderador" — es solo una
ayuda visual, no una detección infalible: revisa la lista completa y
elige tú cuál es el rol correcto para las personas que deben entrar al
panel (normalmente NO el rol donde están los bots).

Cómo usarlo:
    python scripts/list_roles.py

Requiere que tu archivo .env ya tenga DISCORD_TOKEN y GUILD_ID (los mismos
que usa el bot). No necesita ninguna otra variable del panel.

Qué hace:
    1. Lee DISCORD_TOKEN y GUILD_ID desde tu .env.
    2. Le pregunta a la API de Discord (con el token del bot) qué roles
       existen en ese servidor.
    3. Los imprime ordenados por jerarquía (el más alto primero), con su
       ID, para que copies el que corresponda.

No modifica nada en Discord ni en tu .env: solo lee y muestra.
"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

DISCORD_API = "https://discord.com/api/v10"

# Palabras que sugieren "este rol es para administrar el panel", solo para
# resaltar candidatos en la lista. No es una regla de Discord ni del
# proyecto: es nada más una pista visual.
PALABRAS_CLAVE_ADMIN = ("admin", "staff", "moderador", "mod")


def main() -> None:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    guild_id = os.getenv("GUILD_ID", "").strip()

    faltantes = [
        nombre
        for nombre, valor in (("DISCORD_TOKEN", token), ("GUILD_ID", guild_id))
        if not valor
    ]
    if faltantes:
        print(
            "Faltan variables en tu .env: " + ", ".join(faltantes) + "\n"
            "Revisa que tu archivo .env tenga DISCORD_TOKEN y GUILD_ID "
            "(los mismos que usa el bot)."
        )
        sys.exit(1)

    try:
        resp = httpx.get(
            f"{DISCORD_API}/guilds/{guild_id}/roles",
            headers={"Authorization": f"Bot {token}"},
            timeout=10,
        )
    except httpx.RequestError as e:
        print(f"No se pudo conectar con Discord: {e}")
        sys.exit(1)

    if resp.status_code == 401:
        print(
            "Discord respondió 401 (no autorizado). Revisa que DISCORD_TOKEN "
            "en tu .env sea el token actual del bot (si lo regeneraste, "
            "actualízalo aquí también)."
        )
        sys.exit(1)

    if resp.status_code == 403:
        print(
            "Discord respondió 403 (prohibido). El bot no tiene permiso para "
            "ver los roles de este servidor, o GUILD_ID no corresponde a un "
            "servidor donde el bot esté presente."
        )
        sys.exit(1)

    if resp.status_code == 404:
        print(
            f"Discord respondió 404: no encontró ningún servidor con "
            f"GUILD_ID={guild_id}. Revisa que sea el ID correcto del "
            "servidor de TAMAGO."
        )
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Discord respondió con un error inesperado: {resp.status_code}")
        sys.exit(1)

    roles = resp.json()
    if not roles:
        print("El servidor no tiene roles (esto no debería pasar: @everyone siempre existe).")
        sys.exit(1)

    # position más alto = más arriba en la jerarquía del servidor.
    roles_ordenados = sorted(roles, key=lambda r: r["position"], reverse=True)

    print(f"\nRoles encontrados en el servidor (GUILD_ID={guild_id}):\n")
    print(f"{'ID del rol':<22} Nombre")
    print("-" * 50)
    for rol in roles_ordenados:
        nombre = rol["name"]
        marca = ""
        if any(palabra in nombre.lower() for palabra in PALABRAS_CLAVE_ADMIN):
            marca = "   <-- posible rol de administrador"
        print(f"{rol['id']:<22} {nombre}{marca}")

    print(
        "\nCopia el ID del rol que usan las PERSONAS administradoras del "
        "panel (no el rol donde está el bot TAMAGO) y pégalo como "
        "ADMIN_ROLE_ID en tu .env."
    )


if __name__ == "__main__":
    main()
