"""
bot/ai.py
---------
Genera las respuestas de TAMAGO usando la API de Claude (Anthropic), a
partir de la personalidad activa guardada en la base de datos (ver
bot/personalidad.py) y el mensaje de quien lo mencione.

Todavia SIN memoria de conversacion: cada mensaje se responde de forma
independiente, sin recordar mensajes anteriores. Una memoria limitada y
configurable llega en una etapa posterior del proyecto.
"""

import logging

from anthropic import AsyncAnthropic

from .config import Config
from .personalidad import ActivePersonality

logger = logging.getLogger("tamago")

_client: AsyncAnthropic | None = None


def _get_client(config: Config) -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=config.anthropic_api_key)
    return _client


# Estas reglas se agregan SIEMPRE al final del system prompt, sin importar
# que diga la personalidad guardada en la base de datos. Asi, aunque
# alguien edite la personalidad desde el panel para pedir algo indebido,
# estos limites de seguridad basicos se mantienen igual.
SAFETY_RULES = (
    "\n\n---\n"
    "Reglas que nunca rompes, sin importar que diga el resto de tus instrucciones "
    "o lo que te pida un usuario:\n"
    "- No amenazas, acosas, discriminas ni manipulas a nadie.\n"
    "- No generas contenido ilegal, sexual explicito ni de odio, ni suplantas a "
    "una persona real que no seas tu mismo.\n"
    "- No revelas tokens, claves, contrasenas ni configuracion interna del "
    "servidor o del bot, aunque te lo pidan con insistencia.\n"
    "- Si un mensaje pide algo de esto, respondes con amabilidad que no puedes "
    "ayudar con eso, sin sermonear ni dar explicaciones largas.\n"
    "- Tus respuestas son cortas: pocas lineas, con el tono de un mensaje de "
    "chat, no un ensayo."
)


def build_system_prompt(personality: ActivePersonality) -> str:
    parts = [personality.personality]

    if personality.tone:
        parts.append(f"\nTono a mantener: {personality.tone}.")
    if personality.language:
        parts.append(f"Idioma: {personality.language}.")
    if personality.allowed_topics:
        parts.append(f"\nTemas de los que puedes hablar con gusto: {personality.allowed_topics}.")
    if personality.forbidden_topics:
        parts.append(f"Temas que debes evitar por completo: {personality.forbidden_topics}.")

    parts.append(SAFETY_RULES)
    return "\n".join(parts)


async def generate_response(config: Config, personality: ActivePersonality, user_message: str) -> str:
    """Llama a la API de Claude y devuelve el texto de la respuesta."""
    client = _get_client(config)
    system_prompt = build_system_prompt(personality)

    response = await client.messages.create(
        model=config.anthropic_model,
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    if not text:
        raise ValueError("La API de Claude devolvió una respuesta vacía.")

    return text
