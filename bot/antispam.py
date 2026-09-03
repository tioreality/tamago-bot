"""
bot/antispam.py
----------------
Controles anti-spam y anti-bucle para las respuestas de IA de TAMAGO,
siguiendo las reglas de seguridad del proyecto:
- Tiempo de espera (cooldown) entre respuestas, por usuario y canal.
- Limite global de respuestas por minuto (protege el costo de la API).
- Lista de canales autorizados -- por defecto NINGUNO: hay que marcar
  al menos un canal desde la pantalla "Canales" del panel web antes de
  que TAMAGO responda con IA en algun canal.
- Deteccion de mensajes repetidos (el mismo texto, seguido, del mismo
  usuario).
- Interruptor global para apagar las respuestas de IA sin detener el
  bot (comando "!ia off" en Discord, o desde la pantalla
  "Configuracion" del panel -- ambos comparten el mismo valor).
- Prevencion de bucles/spam entre bots: eso se resuelve en bot/client.py
  ignorando CUALQUIER mensaje enviado por un bot (incluido TAMAGO
  mismo), antes de llegar hasta aqui.

El interruptor y la lista de canales ya NO viven en memoria: se leen de
la base de datos en cada mensaje (ver bot/ajustes.py), por eso
check_message() los recibe como parametros en vez de guardarlos aqui.
Lo que SI sigue en memoria del proceso (se reinicia si el bot se
reinicia) son los contadores de cooldown/limite por minuto/mensajes
repetidos: son datos de corto plazo, no hace falta persistirlos.
"""

import time
from collections import deque

_last_response_at: dict[tuple[int, int], float] = {}  # (channel_id, user_id) -> timestamp
_recent_global_responses: deque[float] = deque()
_last_message_by_user: dict[int, str] = {}


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def check_message(
    *,
    channel_id: int,
    user_id: int,
    content: str,
    enabled: bool,
    allowed_channel_ids: frozenset[int],
    cooldown_seconds: int,
    max_responses_per_minute: int,
) -> str | None:
    """
    Decide si TAMAGO deberia responder con IA a este mensaje.
    Devuelve None si puede responder, o un texto corto con el motivo del
    bloqueo (para loguear/guardar) si no deberia responder.
    """
    if not enabled:
        return "interruptor global de IA apagado"

    if channel_id not in allowed_channel_ids:
        return "canal no autorizado para respuestas de IA"

    now = time.monotonic()

    key = (channel_id, user_id)
    last = _last_response_at.get(key)
    if last is not None and (now - last) < cooldown_seconds:
        return "cooldown por usuario todavia activo"

    while _recent_global_responses and now - _recent_global_responses[0] > 60:
        _recent_global_responses.popleft()
    if len(_recent_global_responses) >= max_responses_per_minute:
        return "limite global de respuestas por minuto alcanzado"

    normalized = _normalize(content)
    if normalized and _last_message_by_user.get(user_id) == normalized:
        return "mensaje repetido"

    return None


def register_response(*, channel_id: int, user_id: int, content: str) -> None:
    """Se llama despues de responder, para que los limites de arriba surtan efecto."""
    now = time.monotonic()
    _last_response_at[(channel_id, user_id)] = now
    _recent_global_responses.append(now)
    _last_message_by_user[user_id] = _normalize(content)
