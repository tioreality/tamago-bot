"""
panel/main.py
-------------
Punto de entrada del panel web de TAMAGO. Se ejecuta por separado de
cada bot (es un servicio distinto en Railway), y comparte la misma base
de datos MySQL con todos ellos (ver shared/db.py).

Este panel administra VARIOS bots desde un solo lugar (ver
panel/bots_registry.py para la lista). Las pantallas de un bot en
particular viven bajo /bots/<slug>/... (ej. /bots/tamago/personalidad);
/dashboard es la vista general con un resumen de todos los bots
registrados.

Incluye hasta ahora:
  - Login con Discord (sin contraseñas propias), con verificación de
    rol de administrador.
  - Conexión a la base de datos compartida.
  - Dashboard general (resumen de todos los bots) y un "hub" por bot.
  - Editar personalidad, canales autorizados y configuración (interruptor
    de IA), todo por bot.
  - Ver registros de actividad (bloqueos, errores), por bot.

Todavía NO incluye (llega en etapas siguientes):
  - Conversaciones controladas entre bots (Etapa 3).
  - Apagar/reiniciar cada bot remotamente (Etapa 4).

Cómo correrlo localmente:
    uvicorn panel.main:app --reload --port 8000
Y abrir http://localhost:8000 en el navegador.
"""

import logging
import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import ajustes, bots_registry
from .config import PanelConfigError, load_panel_config
from .auth import AuthError, build_authorize_url, build_avatar_url, exchange_code_for_user, user_is_admin
from .personalidad import PersonalityForm, get_personality, save_personality
from shared.db import BotEvent, DBConfigError, get_engine, init_db, session_scope

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tamago.panel")

templates = Jinja2Templates(directory="panel/templates")

app = FastAPI(title="Panel de TAMAGO")
app.mount("/static", StaticFiles(directory="panel/static"), name="static")

try:
    config = load_panel_config()
    app.add_middleware(SessionMiddleware, secret_key=config.session_secret)
except PanelConfigError as e:
    # No tumbamos el proceso de inmediato: mostramos el error en cada
    # página, para que quien lo despliegue vea exactamente qué falta en
    # vez de un stack trace confuso.
    config = None
    _config_error = str(e)
    app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
else:
    _config_error = None


@app.on_event("startup")
async def _preparar_base_de_datos():
    """Crea las tablas que falten (ej. bot_personalities) al arrancar."""
    if _config_error:
        return
    try:
        init_db()
    except DBConfigError as e:
        logger.warning("No se pudo preparar la base de datos al iniciar: %s", e)
    except Exception as e:  # conexión rechazada, credenciales inválidas, etc.
        logger.warning("Error inesperado preparando la base de datos al iniciar: %s", e)


def _config_check(request: Request):
    if _config_error:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": _config_error},
            status_code=500,
        )
    return None


def _bot_not_found(request: Request, bot_slug: str):
    return templates.TemplateResponse(
        request,
        "error.html",
        {"mensaje": f"No existe ningún bot registrado con el identificador '{bot_slug}'."},
        status_code=404,
    )


def _base_ctx(request: Request, active_page: str, current_bot: bots_registry.BotInfo | None = None) -> dict:
    """Datos que necesita CUALQUIER pantalla del panel una vez con sesión
    iniciada: usuario, avatar, qué link resaltar en el sidebar, la lista
    completa de bots (para el selector) y -- si aplica -- de cuál bot se
    está hablando en esta pantalla."""
    return {
        "username": request.session.get("username"),
        "avatar_url": request.session.get("avatar_url"),
        "active_page": active_page,
        "bots": bots_registry.BOTS,
        "current_bot": current_bot,
        # {slug: avatar_url} de cada bot que ya se conecto al menos una
        # vez a Discord -- una sola consulta, reusada por el sidebar
        # (lista "Tus bots") y por el encabezado de la pagina actual.
        "avatares": ajustes.get_avatar_urls([b.slug for b in bots_registry.BOTS]),
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    error = _config_check(request)
    if error:
        return error

    if request.session.get("user_id"):
        return RedirectResponse("/dashboard")

    return templates.TemplateResponse(request, "login.html")


@app.get("/login")
async def login(request: Request):
    error = _config_check(request)
    if error:
        return error

    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(build_authorize_url(config, state))


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    err = _config_check(request)
    if err:
        return err

    if error:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "Inicio de sesión cancelado en Discord."},
            status_code=400,
        )

    if not code or state != request.session.get("oauth_state"):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "La solicitud de login no es válida. Intenta de nuevo desde /login."},
            status_code=400,
        )

    try:
        discord_user = await exchange_code_for_user(config, code)
        es_admin = await user_is_admin(config, discord_user["id"])
    except AuthError as e:
        return templates.TemplateResponse(
            request, "error.html", {"mensaje": str(e)}, status_code=502
        )

    if not es_admin:
        logger.info("Acceso denegado al panel para usuario de Discord %s", discord_user.get("id"))
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "mensaje": "Tu cuenta de Discord no tiene el rol de administrador en el servidor de TAMAGO, así que no puedes entrar al panel.",
            },
            status_code=403,
        )

    request.session["user_id"] = discord_user["id"]
    request.session["username"] = discord_user.get("username", "Admin")
    request.session["avatar_url"] = build_avatar_url(discord_user)
    logger.info("Login exitoso en el panel: %s (%s)", discord_user.get("username"), discord_user["id"])
    return RedirectResponse("/dashboard")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    db_status = "conectada"
    try:
        with get_engine().connect():
            pass
    except DBConfigError as e:
        db_status = f"no configurada ({e})"
    except Exception as e:  # conexión rechazada, credenciales inválidas, etc.
        db_status = f"error de conexión ({e})"

    # Un resumen rápido de cada bot registrado, para las tarjetas del
    # dashboard. Si la base de datos no responde, cada tarjeta queda
    # "sin datos" -- el problema ya se ve arriba, en la tarjeta de
    # "Base de datos".
    bots_resumen = []
    for bot in bots_registry.BOTS:
        personalidad_nombre = None
        ai_enabled = None
        canales_count = None
        if db_status == "conectada":
            try:
                personalidad_nombre = get_personality(bot.slug).name or None
            except Exception:
                pass
            try:
                settings = ajustes.get_settings(bot.slug)
                ai_enabled = settings.ai_enabled
                canales_count = len(settings.allowed_channel_ids)
            except Exception:
                pass
        bots_resumen.append(
            {
                "bot": bot,
                "personalidad_nombre": personalidad_nombre,
                "ai_enabled": ai_enabled,
                "canales_count": canales_count,
            }
        )

    ctx = _base_ctx(request, "dashboard")
    ctx.update({"db_status": db_status, "bots_resumen": bots_resumen})
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@app.get("/bots/{bot_slug}", response_class=HTMLResponse)
async def bot_hub(request: Request, bot_slug: str):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    personalidad_nombre = None
    ai_enabled = None
    canales_count = None
    try:
        personalidad_nombre = get_personality(bot.slug).name or None
    except Exception:
        pass
    try:
        settings = ajustes.get_settings(bot.slug)
        ai_enabled = settings.ai_enabled
        canales_count = len(settings.allowed_channel_ids)
    except Exception:
        pass

    ctx = _base_ctx(request, "bot_hub", current_bot=bot)
    ctx.update(
        {
            "personalidad_nombre": personalidad_nombre,
            "ai_enabled": ai_enabled,
            "canales_count": canales_count,
        }
    )
    return templates.TemplateResponse(request, "bot_hub.html", ctx)


@app.get("/bots/{bot_slug}/registros", response_class=HTMLResponse)
async def registros(request: Request, bot_slug: str):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    eventos = []
    error_registros = None
    try:
        with session_scope() as session:
            filas = (
                session.query(BotEvent)
                .filter_by(bot_slug=bot.slug)
                .order_by(BotEvent.created_at.desc())
                .limit(50)
                .all()
            )
            eventos = [
                {
                    "fecha": fila.created_at.strftime("%d/%m/%Y %H:%M:%S") if fila.created_at else "--",
                    "tipo": fila.event_type,
                    "descripcion": fila.description,
                    "canal_id": fila.channel_id,
                    "usuario_id": fila.user_id,
                }
                for fila in filas
            ]
    except DBConfigError as e:
        error_registros = str(e)
    except Exception as e:
        logger.error("Error leyendo registros de '%s' desde la base de datos: %s", bot.slug, e)
        error_registros = "No se pudieron leer los registros desde la base de datos. Intenta de nuevo."

    ctx = _base_ctx(request, "registros", current_bot=bot)
    ctx.update({"eventos": eventos, "error_registros": error_registros})
    return templates.TemplateResponse(request, "registros.html", ctx)


@app.get("/bots/{bot_slug}/personalidad", response_class=HTMLResponse)
async def personalidad_form(request: Request, bot_slug: str):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    try:
        data = get_personality(bot.slug)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error leyendo la personalidad de '%s' desde la base de datos: %s", bot.slug, e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudo leer la personalidad desde la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    ctx = _base_ctx(request, "personalidad", current_bot=bot)
    ctx.update({"personalidad": data, "guardado": False})
    return templates.TemplateResponse(request, "personalidad.html", ctx)


@app.post("/bots/{bot_slug}/personalidad", response_class=HTMLResponse)
async def personalidad_guardar(
    request: Request,
    bot_slug: str,
    name: str = Form(...),
    description: str = Form(""),
    personality: str = Form(...),
    tone: str = Form(""),
    language: str = Form(""),
    allowed_topics: str = Form(""),
    forbidden_topics: str = Form(""),
    presentation_message: str = Form(""),
):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    data = PersonalityForm(
        bot_slug=bot.slug,
        name=name.strip(),
        description=description.strip(),
        personality=personality.strip(),
        tone=tone.strip(),
        language=language.strip(),
        allowed_topics=allowed_topics.strip(),
        forbidden_topics=forbidden_topics.strip(),
        presentation_message=presentation_message.strip(),
    )

    if not data.name or not data.personality:
        ctx = _base_ctx(request, "personalidad", current_bot=bot)
        ctx.update(
            {
                "personalidad": data,
                "guardado": False,
                "error_validacion": "El nombre y el texto de personalidad son obligatorios.",
            }
        )
        return templates.TemplateResponse(request, "personalidad.html", ctx, status_code=400)

    try:
        save_personality(data)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error guardando la personalidad de '%s' en la base de datos: %s", bot.slug, e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudo guardar la personalidad en la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    logger.info(
        "Personalidad de '%s' actualizada desde el panel por %s",
        data.bot_slug,
        request.session.get("username"),
    )
    ctx = _base_ctx(request, "personalidad", current_bot=bot)
    ctx.update({"personalidad": data, "guardado": True})
    return templates.TemplateResponse(request, "personalidad.html", ctx)


@app.get("/bots/{bot_slug}/canales", response_class=HTMLResponse)
async def canales_form(request: Request, bot_slug: str):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    try:
        settings = ajustes.get_settings(bot.slug)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error leyendo canales de '%s' desde la base de datos: %s", bot.slug, e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudieron leer los canales desde la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    canales_disponibles = await ajustes.fetch_guild_text_channels(config)

    ctx = _base_ctx(request, "canales", current_bot=bot)
    ctx.update(
        {
            "canales_disponibles": canales_disponibles,
            "canales_guardados": set(settings.allowed_channel_ids),
            "canales_guardados_raw": "\n".join(settings.allowed_channel_ids),
            "guardado": False,
        }
    )
    return templates.TemplateResponse(request, "canales.html", ctx)


@app.post("/bots/{bot_slug}/canales", response_class=HTMLResponse)
async def canales_guardar(request: Request, bot_slug: str):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    form = await request.form()
    seleccionados = form.getlist("canal_id")
    if not seleccionados:
        # Modo manual (cuando no se pudo cargar la lista de canales de
        # Discord): un ID de canal por línea.
        manual = str(form.get("canales_manual", ""))
        seleccionados = [
            pedazo.strip()
            for pedazo in manual.replace(",", "\n").splitlines()
            if pedazo.strip()
        ]

    invalidos = [c for c in seleccionados if not c.isdigit()]
    canales_disponibles = await ajustes.fetch_guild_text_channels(config)

    if invalidos:
        ctx = _base_ctx(request, "canales", current_bot=bot)
        ctx.update(
            {
                "canales_disponibles": canales_disponibles,
                "canales_guardados": set(seleccionados),
                "canales_guardados_raw": "\n".join(seleccionados),
                "guardado": False,
                "error_validacion": (
                    "Estos valores no parecen IDs de canal válidos (deben ser solo "
                    "números): " + ", ".join(invalidos)
                ),
            }
        )
        return templates.TemplateResponse(request, "canales.html", ctx, status_code=400)

    try:
        ajustes.save_allowed_channels(bot.slug, seleccionados)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error guardando canales de '%s' en la base de datos: %s", bot.slug, e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudieron guardar los canales en la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    logger.info(
        "Canales autorizados de '%s' actualizados desde el panel por %s: %s",
        bot.slug,
        request.session.get("username"),
        seleccionados,
    )

    ctx = _base_ctx(request, "canales", current_bot=bot)
    ctx.update(
        {
            "canales_disponibles": canales_disponibles,
            "canales_guardados": set(seleccionados),
            "canales_guardados_raw": "\n".join(seleccionados),
            "guardado": True,
        }
    )
    return templates.TemplateResponse(request, "canales.html", ctx)


@app.get("/bots/{bot_slug}/configuracion", response_class=HTMLResponse)
async def configuracion_form(request: Request, bot_slug: str):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    try:
        settings = ajustes.get_settings(bot.slug)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error leyendo la configuración de '%s' desde la base de datos: %s", bot.slug, e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudo leer la configuración desde la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    ctx = _base_ctx(request, "configuracion", current_bot=bot)
    ctx.update(
        {
            "ai_enabled": settings.ai_enabled,
            "canales_count": len(settings.allowed_channel_ids),
            "guardado": False,
        }
    )
    return templates.TemplateResponse(request, "configuracion.html", ctx)


@app.post("/bots/{bot_slug}/configuracion", response_class=HTMLResponse)
async def configuracion_guardar(request: Request, bot_slug: str, ai_enabled: str | None = Form(None)):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    bot = bots_registry.get_bot(bot_slug)
    if bot is None:
        return _bot_not_found(request, bot_slug)

    # Un checkbox sin marcar no se manda en el formulario -- por eso el
    # valor por defecto es None (no "off"), y "activado" es simplemente
    # "¿llegó el campo o no?".
    valor = ai_enabled is not None

    try:
        ajustes.save_ai_enabled(bot.slug, valor)
        settings = ajustes.get_settings(bot.slug)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error guardando la configuración de '%s' en la base de datos: %s", bot.slug, e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudo guardar la configuración en la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    logger.info(
        "Interruptor global de IA de '%s' cambiado a %s desde el panel por %s",
        bot.slug,
        "activado" if valor else "desactivado",
        request.session.get("username"),
    )

    ctx = _base_ctx(request, "configuracion", current_bot=bot)
    ctx.update(
        {
            "ai_enabled": settings.ai_enabled,
            "canales_count": len(settings.allowed_channel_ids),
            "guardado": True,
        }
    )
    return templates.TemplateResponse(request, "configuracion.html", ctx)


# --- Atajos de compatibilidad -----------------------------------------
# Antes de que el panel administrara varios bots, estas pantallas vivían
# en /personalidad, /canales, etc. (sin bot_slug). Se dejan como redirect
# al bot "tamago" por si alguien tiene un enlace o marcador guardado.


@app.get("/personalidad")
async def _personalidad_legacy():
    return RedirectResponse("/bots/tamago/personalidad")


@app.get("/canales")
async def _canales_legacy():
    return RedirectResponse("/bots/tamago/canales")


@app.get("/configuracion")
async def _configuracion_legacy():
    return RedirectResponse("/bots/tamago/configuracion")


@app.get("/registros")
async def _registros_legacy():
    return RedirectResponse("/bots/tamago/registros")


@app.get("/health")
async def health():
    """Endpoint simple para que Railway confirme que el servicio está vivo."""
    return {"status": "ok"}
