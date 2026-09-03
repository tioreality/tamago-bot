"""
scripts/migrate_add_bot_slug_to_bot_events.py
-----------------------------------------------
Migración única: agrega la columna "bot_slug" a la tabla "bot_events" en
la base de datos MySQL real, para poder filtrar los registros de
actividad por bot ahora que el panel administra varios bots.

Segura de correr más de una vez: si la columna ya existe, no hace nada.
No borra ni modifica ningún dato existente.

Cómo usarlo (desde tu PowerShell, con el venv activado, parado en la
carpeta del proyecto):
    python scripts/migrate_add_bot_slug_to_bot_events.py

Por qué lo tienes que correr tú y no el asistente: este script necesita
conectarse a tu base de datos real en Hostinger, y ni el entorno del
puente con tu computadora ni el contenedor en la nube tienen salida de
red hacia ese servidor (la misma limitación que ya vimos antes con el
resto de la base de datos).

Qué hace exactamente:
    1. Revisa si la tabla "bot_events" ya tiene la columna "bot_slug".
    2. Si no la tiene, la agrega como VARCHAR(50) NOT NULL, con
       'tamago' como valor por defecto -- así las filas que ya existen
       (hasta ahora, todas de TAMAGO) quedan marcadas correctamente sin
       que tengas que hacer nada más.
"""

import sys
from pathlib import Path

# Al ejecutar este archivo directamente (python scripts/migrate_....py),
# Python solo agrega la carpeta "scripts/" a su lista de búsqueda de
# módulos, no la raíz del proyecto -- y ahí es donde vive el paquete
# "shared" que este script necesita. Esta línea agrega esa carpeta raíz
# (un nivel arriba de "scripts/") a la búsqueda, para que el import de
# abajo funcione sin importar desde dónde llames al script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text

from shared.db import DBConfigError, get_engine

# bot/config.py y panel/config.py cargan el archivo ".env" apenas arrancan
# (con load_dotenv()); este script es independiente de ambos, así que sin
# esta línea nunca se leen MYSQL_HOST/MYSQL_USER/etc. y la conexión falla
# como si el .env no existiera, aunque sí exista.
load_dotenv()


def main() -> None:
    try:
        engine = get_engine()
    except DBConfigError as e:
        print(f"Falta configuración de base de datos: {e}")
        sys.exit(1)

    try:
        with engine.connect() as conn:
            database = conn.execute(text("SELECT DATABASE()")).scalar()
            existe = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = :db AND table_name = 'bot_events' "
                    "AND column_name = 'bot_slug'"
                ),
                {"db": database},
            ).scalar()

            if existe:
                print("La columna 'bot_slug' ya existe en 'bot_events'. No hay nada que hacer.")
                return

            print("Agregando la columna 'bot_slug' a 'bot_events' (valor por defecto: 'tamago')...")
            conn.execute(
                text(
                    "ALTER TABLE bot_events "
                    "ADD COLUMN bot_slug VARCHAR(50) NOT NULL DEFAULT 'tamago'"
                )
            )
            conn.commit()
            print("Listo. Las filas existentes quedaron marcadas como 'tamago'.")
    except Exception as e:
        print(f"No se pudo aplicar la migración: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
