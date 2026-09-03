"""
scripts/migrate_add_avatar_url_to_bot_settings.py
----------------------------------------------------
Migracion unica: agrega la columna "avatar_url" a la tabla "bot_settings"
en la base de datos MySQL real, para que el panel pueda mostrar la foto
de perfil real de cada bot en vez de un emoji generico.

Segura de correr mas de una vez: si la columna ya existe, no hace nada.
No borra ni modifica ningun dato existente.

Como usarlo (desde tu PowerShell, con el venv activado, parado en la
carpeta del proyecto):
    python scripts/migrate_add_avatar_url_to_bot_settings.py

Que hace exactamente:
    1. Revisa si la tabla "bot_settings" ya tiene la columna "avatar_url".
    2. Si no la tiene, la agrega como VARCHAR(500), sin valor por
       defecto (queda NULL para las filas existentes hasta que cada bot
       se conecte una vez y la complete solo -- ver bot/client.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text

from shared.db import DBConfigError, get_engine

load_dotenv()


def main() -> None:
    try:
        engine = get_engine()
    except DBConfigError as e:
        print(f"Falta configuracion de base de datos: {e}")
        sys.exit(1)

    try:
        with engine.connect() as conn:
            database = conn.execute(text("SELECT DATABASE()")).scalar()
            existe = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = :db AND table_name = 'bot_settings' "
                    "AND column_name = 'avatar_url'"
                ),
                {"db": database},
            ).scalar()

            if existe:
                print("La columna 'avatar_url' ya existe en 'bot_settings'. No hay nada que hacer.")
                return

            print("Agregando la columna 'avatar_url' a 'bot_settings'...")
            conn.execute(
                text("ALTER TABLE bot_settings ADD COLUMN avatar_url VARCHAR(500) NULL")
            )
            conn.commit()
            print("Listo. Cada bot completara su propia foto la proxima vez que se conecte.")
    except Exception as e:
        print(f"No se pudo aplicar la migracion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
