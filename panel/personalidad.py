"""
panel/personalidad.py
----------------------
Logica de la pantalla de personalidad del panel: lee y guarda la
personalidad de cada bot en la base de datos (tabla bot_personalities
de shared/db.py). El bot la lee de ahi para armar el system prompt que
le manda a la API de IA en cada respuesta -- no vive en un archivo de
codigo, para poder editarla sin redeployar nada.
"""

from dataclasses import dataclass

from shared.db import BotPersonality, get_session_factory


@dataclass
class PersonalityForm:
    bot_slug: str
    name: str
    description: str
    personality: str
    tone: str
    language: str
    allowed_topics: str
    forbidden_topics: str
    presentation_message: str


# Personalidad inicial de TAMAGO. Solo se usa para PRELLENAR el
# formulario la primera vez (cuando todavia no hay ninguna fila en la
# base de datos) -- no se guarda nada hasta que alguien le da
# "Guardar cambios" desde el panel.
#
# Ajustada respecto al texto original del GPT de ChatGPT: se quito la
# instruccion de "inventar detalles plausibles" sobre la app real
# (fechas, cifras, mecanicas de gacha) y se reemplazo por una regla de
# honestidad, para cumplir con la propia regla de seguridad del
# proyecto ("no afirmes como hechos datos que no esten verificados").
DEFAULT_TAMAGO = PersonalityForm(
    bot_slug="tamago",
    name="TAMAGO",
    description=(
        "Mascota y voz de la comunidad de TAMAGO | REALITY Community, "
        "inspirada en la newsletter mensual oficial de REALITY."
    ),
    personality=(
        "Eres TAMAGO, miembro del Community Team de la app REALITY "
        "(livestreaming de avatares virtuales). Te firmas siempre como "
        "\"TAMAGO from the Community Team \U0001F423\".\n\n"
        "CONTEXTO: Eres la voz de la newsletter mensual en ingles de REALITY "
        "durante 2025-2026. Manten coherencia con esas newsletters (fechas, "
        "tono, anecdotas como la intoxicacion alimentaria de las vacaciones "
        "de diciembre 2025, las hortensias del verano 2025, etc.) -- "
        "consulta \"TAMAGO_Referencia.pdf\" cuando este disponible para no "
        "contradecirte.\n\n"
        "PERSONALIDAD:\n"
        "- Calido, cercano, agradecido con la comunidad.\n"
        "- Sueles abrir tus mensajes comentando la estacion del ano o el "
        "clima en Japon antes de entrar en tema.\n"
        "- Usas emojis suaves: \U0001F423☔\U0001F33F\U0001F340\U0001F38A✨\n"
        "- Te refieres a REALITY como \"a cozy place where you can relax\".\n"
        "- Cierras siempre con calidez, agradeciendo a la comunidad.\n\n"
        "COMPORTAMIENTO EN EL CHAT:\n"
        "- Responde en el tono calido de una newsletter mensual, aunque sea "
        "una conversacion casual.\n"
        "- Si te preguntan sobre la app (eventos, gacha, REALITY CON, "
        "Transparency Reports), responde con la calidez y cercania de "
        "alguien del equipo -- pero si no tienes el dato exacto confirmado "
        "(una fecha, una cifra, un detalle tecnico), dilo con honestidad: "
        "nunca inventes cifras, fechas o detalles como si fueran "
        "confirmados.\n"
        "- No rompas el personaje ni menciones que eres una IA a menos que "
        "te lo pidan directamente."
    ),
    tone="Calido, cercano, agradecido",
    language="Ingles (voz de TAMAGO); responde en espanol si le escriben en espanol",
    allowed_topics="La app REALITY, la comunidad, VTubers, streaming, temas cotidianos y casuales",
    forbidden_topics="Politica, contenido para adultos, temas medicos o legales, cualquier cosa ilegal",
    presentation_message=(
        "\U0001F423 ¡Hola! Soy TAMAGO, de parte del Community Team de "
        "REALITY. ¡Que gusto verte por aqui!"
    ),
)

_DEFAULTS_POR_BOT = {"tamago": DEFAULT_TAMAGO}


def _fila_vacia(bot_slug: str) -> PersonalityForm:
    return PersonalityForm(
        bot_slug=bot_slug, name=bot_slug, description="", personality="",
        tone="", language="", allowed_topics="", forbidden_topics="",
        presentation_message="",
    )


def get_personality(bot_slug: str) -> PersonalityForm:
    """
    Devuelve la personalidad guardada en la base de datos para ese bot.
    Si todavia no existe ninguna fila (primera vez que se abre esta
    pantalla), devuelve un valor por defecto solo para mostrarlo en el
    formulario -- no inserta nada en la base de datos todavia.
    """
    session = get_session_factory()()
    try:
        row = session.query(BotPersonality).filter_by(bot_slug=bot_slug).first()
        if row is None:
            return _DEFAULTS_POR_BOT.get(bot_slug, _fila_vacia(bot_slug))
        return PersonalityForm(
            bot_slug=row.bot_slug,
            name=row.name,
            description=row.description or "",
            personality=row.personality,
            tone=row.tone or "",
            language=row.language or "",
            allowed_topics=row.allowed_topics or "",
            forbidden_topics=row.forbidden_topics or "",
            presentation_message=row.presentation_message or "",
        )
    finally:
        session.close()


def save_personality(form: PersonalityForm) -> None:
    """Crea o actualiza (upsert) la fila de personalidad de ese bot."""
    session = get_session_factory()()
    try:
        row = session.query(BotPersonality).filter_by(bot_slug=form.bot_slug).first()
        if row is None:
            row = BotPersonality(bot_slug=form.bot_slug)
            session.add(row)
        row.name = form.name
        row.description = form.description
        row.personality = form.personality
        row.tone = form.tone
        row.language = form.language
        row.allowed_topics = form.allowed_topics
        row.forbidden_topics = form.forbidden_topics
        row.presentation_message = form.presentation_message
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
