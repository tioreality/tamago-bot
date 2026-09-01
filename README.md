# TAMAGO — Bot oficial de Discord (Etapa 1: MVP)

Bot oficial (cuenta de tipo *bot*, creada en el Discord Developer Portal) para
el servidor **TAMAGO | REALITY Community**. Esta primera versión no tiene
personalidad, IA ni conversación entre bots todavía — eso llega en las
siguientes etapas. El único objetivo de esta etapa es demostrar que el bot
se conecta, responde y se puede detener de forma segura.

## 1. Qué hace esta versión

- Se conecta a Discord con un token oficial de bot.
- Responde al comando `!ping` con un mensaje de confirmación.
- Registra su actividad técnica en `logs/tamago.log`.
- Se detiene de forma limpia con `Ctrl+C`.

No incluye todavía: comandos slash, personalidad, respuestas con IA,
conversaciones entre bots ni base de datos. Eso corresponde a las etapas 2,
3 y 4 descritas en el plan del proyecto.

## 2. Requisitos previos

- **Python 3.10 o superior** instalado ([python.org](https://www.python.org/downloads/)).
  Verifica con: `python --version` (o `python3 --version` en macOS/Linux).
- Una cuenta de Discord con permisos de administrador en el servidor donde
  vas a probar el bot.
- Git es opcional (solo si quieres versionar el proyecto).

## 3. Crear la aplicación y el bot en Discord

1. Entra a <https://discord.com/developers/applications> con tu cuenta.
2. Clic en **New Application**, ponle un nombre (por ejemplo `TAMAGO`) y acepta los términos.
3. En el menú lateral, ve a **Bot**.
4. Clic en **Reset Token** (o **Add Bot** si es la primera vez) y copia el token.
   - **Este token es una contraseña.** No lo compartas, no lo subas a git, no lo pegues en chats públicos.
   - Si alguna vez se filtra, vuelve a esta pantalla y pulsa **Reset Token** de nuevo para invalidarlo.
5. En la misma pantalla, baja hasta **Privileged Gateway Intents** y activa:
   - ✅ **Message Content Intent** (necesario para que el bot pueda leer `!ping`).
   - Los otros dos (Presence, Server Members) no son necesarios en esta etapa: déjalos apagados.
6. Guarda los cambios.

### Permisos mínimos para invitar el bot

1. Ve a **OAuth2 > URL Generator**.
2. En **Scopes**, marca: `bot`.
3. En **Bot Permissions**, marca solo lo mínimo necesario para esta etapa:
   - ✅ View Channels (Ver canales)
   - ✅ Send Messages (Enviar mensajes)
   - ✅ Read Message History (Leer historial de mensajes)
   - (No marques permisos de administración, gestión del servidor, banear, etc. No los necesita.)
4. Copia la URL generada al final de la página, ábrela en el navegador, elige tu servidor y confirma.

## 4. Instalar el proyecto en tu computadora

Descomprime el proyecto y abre una terminal dentro de la carpeta `tamago-bot/`.

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Después, abre el archivo `.env` con un editor de texto y reemplaza
`tu_token_aqui` por el token real que copiaste en el paso 3. Deja las demás
variables como están (son opcionales en esta etapa).

**El archivo `.env` nunca se debe compartir ni subir a git** (ya está
excluido en `.gitignore`).

## 5. Ejecutar el bot

Con el entorno virtual activado (verás `(venv)` al inicio de la línea de la terminal):

```bash
python run.py
```

Deberías ver en la terminal algo como:

```
2026-09-01 12:00:00 | INFO     | tamago | Iniciando TAMAGO...
2026-09-01 12:00:01 | INFO     | tamago | Conectado como TAMAGO#1234 (ID: ...)
2026-09-01 12:00:01 | INFO     | tamago | Prefijo de comandos activo: !
```

## 6. Cómo probar que funciona

1. Ve al servidor de Discord donde invitaste al bot.
2. En un canal donde el bot tenga acceso, escribe: `!ping`
3. Resultado esperado: el bot responde `🏓 Pong! Soy TAMAGO y estoy en línea, @tu_usuario.`
4. Revisa la terminal: debería aparecer una línea de log indicando que se usó el comando.

## 7. Cómo detener el bot de forma segura

En la terminal donde está corriendo, presiona **Ctrl+C**. El bot cierra la
conexión con Discord de forma ordenada antes de terminar el proceso. No hay
que "matar" el proceso de otra forma en esta etapa.

## 8. Errores comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `[ERROR DE CONFIGURACIÓN] Falta DISCORD_TOKEN...` | No copiaste `.env.example` a `.env`, o dejaste el valor de ejemplo | Copia el archivo y pega el token real |
| `El token de Discord fue rechazado` | Token incorrecto, con espacios, o revocado | Vuelve al Developer Portal, genera uno nuevo (Reset Token) y pégalo de nuevo |
| `Falta activar un intent privilegiado...` | No activaste "Message Content Intent" | Developer Portal > Bot > Privileged Gateway Intents |
| El bot se conecta pero no responde a `!ping` | El bot no tiene permiso de ver/enviar mensajes en ese canal, o usaste otro prefijo | Revisa permisos del canal y el valor de `COMMAND_PREFIX` en `.env` |
| `ModuleNotFoundError: No module named 'discord'` | El entorno virtual no está activado o no se instalaron dependencias | Activa `venv` y ejecuta `pip install -r requirements.txt` de nuevo |
| `python: command not found` | Python no está instalado o no está en el PATH | Reinstala Python marcando la opción "Add to PATH" (Windows) |

## 9. Privacidad: qué datos se guardan

- **Se guarda:** registros técnicos en `logs/tamago.log` — hora, evento
  (conexión, comando usado), nombre de usuario y canal donde se usó un
  comando. Sirve solo para depurar problemas.
- **No se guarda:** el contenido de mensajes normales (solo se procesan en
  memoria para detectar comandos, no se almacenan), tokens, claves de API,
  ni ningún dato personal adicional.
- **Cómo borrar los datos guardados:** con el bot detenido, borra el
  contenido de la carpeta `logs/`. Se recreará automáticamente la próxima
  vez que inicies el bot.
- Esta etapa no usa todavía ninguna base de datos (SQLite se incorporará
  más adelante, cuando se implemente memoria de conversación limitada,
  según el plan del proyecto).

## 10. Estructura del proyecto

```
tamago-bot/
├── .env.example       # Plantilla de configuración (sin secretos reales)
├── .env                # Tu configuración real (la creas tú, nunca se sube a git)
├── .gitignore          # Excluye .env, logs y entornos virtuales del control de versiones
├── requirements.txt    # Dependencias de Python
├── run.py              # Punto de entrada: arranca el bot
├── bot/
│   ├── __init__.py
│   ├── config.py        # Carga y valida las variables de entorno
│   ├── logger.py         # Configura los registros (consola + archivo)
│   └── client.py          # Define el bot y sus comandos (ping, manejo de errores)
├── logs/
│   └── tamago.log        # Se genera al ejecutar el bot (no se versiona)
└── data/                 # Reservado para la futura base de datos SQLite (Etapa 4)
```

## 11. Próximos pasos (siguientes etapas del plan)

- **Etapa 2:** comandos slash, personalidad configurable, respuestas con una API de IA, configuración por servidor/canal.
- **Etapa 3:** un segundo bot con personalidad distinta y conversaciones entre bots (con límites de turnos y tiempo).
- **Etapa 4:** moderación, memoria limitada, manejo avanzado de errores y preparación para alojamiento 24/7.

No avanzaremos a la Etapa 2 hasta confirmar que este MVP funciona correctamente en tu entorno.
