"""
scripts/check_role_permissions.py
----------------------------------
Script de diagnóstico (no forma parte del panel ni del bot): muestra
todos los permisos de Discord (activos e inactivos) de un rol específico
del servidor, para revisar si le falta alguno.

Cómo usarlo:
    python scripts/check_role_permissions.py                 (usa el rol de ADMIN_ROLE_ID en tu .env)
    python scripts/check_role_permissions.py 1544672700646293604   (usa el ID de rol que le pases)

Requiere que tu archivo .env tenga DISCORD_TOKEN y GUILD_ID (los mismos
que usa el bot). No modifica nada en Discord ni en tu .env: solo lee y
muestra.
"""

import os
import sys

import discord
import httpx
from dotenv import load_dotenv

load_dotenv()

DISCORD_API = "https://discord.com/api/v10"


def main() -> None:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    guild_id = os.getenv("GUILD_ID", "").strip()
    role_id = sys.argv[1].strip() if len(sys.argv) > 1 else os.getenv("ADMIN_ROLE_ID", "").strip()

    faltantes = [
        nombre
        for nombre, valor in (
            ("DISCORD_TOKEN", token),
            ("GUILD_ID", guild_id),
            ("ID de rol (ADMIN_ROLE_ID o argumento)", role_id),
        )
        if not valor
    ]
    if faltantes:
        print("Falta: " + ", ".join(faltantes))
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

    if resp.status_code != 200:
        print(f"Discord respondió con un error: {resp.status_code} — {resp.text}")
        sys.exit(1)

    roles = resp.json()
    target = next((r for r in roles if r["id"] == role_id), None)
    if target is None:
        print(f"No se encontró ningún rol con ID {role_id} en este servidor.")
        sys.exit(1)

    perms = discord.Permissions(int(target["permissions"]))
    activos = sorted(nombre for nombre, valor in perms if valor)
    inactivos = sorted(nombre for nombre, valor in perms if not valor)

    print(f"\nRol: {target['name']}  (ID: {target['id']})\n")
    print(f"Permisos ACTIVOS ({len(activos)}):")
    for p in activos:
        print(f"  ✔ {p}")
    print(f"\nPermisos INACTIVOS ({len(inactivos)}):")
    for p in inactivos:
        print(f"  ✘ {p}")


if __name__ == "__main__":
    main()
