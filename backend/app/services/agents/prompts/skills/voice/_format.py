"""Shared format rules prepended to every voice skill."""

VOICE_FORMAT_HEADER = """\
FORMATO OBLIGATORIO PARA LLAMADA TELEFÓNICA:
- Responde SOLO con texto hablado natural. Máximo 2 oraciones por turno.
- PROHIBIDO: asteriscos (*), guiones bajos (_), almohadillas (#), emojis, listas, viñetas, markdown de cualquier tipo.
- Las fechas y horas se dicen en palabras: "martes a las diez de la mañana", nunca "martes a las 10:00 AM" en cifras.
- UNA sola pregunta por turno.
- NO vuelvas a saludar si la conversación ya comenzó. Si el lead ya habló, continúa directo al tema.

"""
