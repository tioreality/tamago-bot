"""
panel/main.py
-------------
Punto de entrada del panel web de TAMAGO. Se ejecuta por separado del
bot (es un servicio distinto en Railway), y comparte la misma base de
datos MySQL (ver shared/db.py).

Esta primera versión (Sub-etapa 1) solo prueba que la base más difícil
ya funciona:
  - Login con Discord (sin contraseñas propias).
  - Verificación de que quien entra tiene el rol de administrador.
  - Conexión a la base de datos compartida.

Todavía NO incluye (llega en las siguientes sub-etapas):
  - Editar personalidad.
  - Configurar canales/permisos por servidor.
  - Ver logs de actividad.
  - Apagar/reiniciar el bot.

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

from .config import PanelConfigError, load_panel_config
from .auth import AuthError, build_authorize_url, exchange_code_for_user, user_is_admin
from .personalidad import PersonalityForm, get_personality, save_personality
from shared.db import DBConfigError, get_engine, init_db

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

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "username": request.session.get("username"),
            "db_status": db_status,
        },
    )


@app.get("/personalidad", response_class=HTMLResponse)
async def personalidad_form(request: Request):
    error = _config_check(request)
    if error:
        return error

    if not request.session.get("user_id"):
        return RedirectResponse("/")

    try:
        data = get_personality("tamago")
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error leyendo la personalidad desde la base de datos: %s", e)
        return templates.TemplateResponse(
            request,
            "error.html",
            {"mensaje": "No se pudo leer la personalidad desde la base de datos. Intenta de nuevo."},
            status_code=502,
        )

    return templates.TemplateResponse(
        request,
        "personalidad.html",
        {"username": request.session.get("username"), "personalidad": data, "guardado": False},
    )


@app.post("/personalidad", response_class=HTMLResponse)
async def personalidad_guardar(
    request: Request,
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

    data = PersonalityForm(
        bot_slug="tamago",
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
        return templates.TemplateResponse(
            request,
            "personalidad.html",
            {
                "username": request.session.get("username"),
                "personalidad": data,
                "guardado": False,
                "error_validacion": "El nombre y el texto de personalidad son obligatorios.",
            },
            status_code=400,
        )

    try:
        save_personality(data)
    except DBConfigError as e:
        return templates.TemplateResponse(request, "error.html", {"mensaje": str(e)}, status_code=500)
    except Exception as e:
        logger.error("Error guardando la personalidad en la base de datos: %s", e)
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
    return templates.TemplateResponse(
        request,
        "personalidad.html",
        {"username": request.session.get("username"), "personalidad": data, "guardado": True},
    )


@app.get("/health")
async def health():
    """Endpoint simple para que Railway confirme que el servicio está vivo."""
    return {"status": "ok"}
