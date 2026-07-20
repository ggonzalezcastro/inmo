"""Per-purpose call objective blocks injected into voice prompts.

Keyed by CallPurpose values (app.models.voice_call.CallPurpose). Same voice
style as the agent voice skills: plain spoken Spanish, numbers in words,
no markdown, no emojis.
"""

from typing import Optional

PURPOSE_INSTRUCTIONS = {
    "calificacion_inicial": """\
El objetivo de esta llamada es la calificacion inicial del lead. \
Descubre que tipo de propiedad busca, en que zona, su presupuesto aproximado y su disponibilidad para una visita. \
No intentes agendar todavia si faltan datos basicos. Manten la llamada corta y amable.""",
    "calificacion_financiera": """\
El objetivo de esta llamada es la calificacion financiera del lead. \
Pregunta con tacto por sus ingresos aproximados, capacidad de pago y si tiene pre aprobacion bancaria. \
Nunca prometas pre aprobacion ni financiamiento. Si el lead esta en DICOM, no ofrezcas ninguna promesa de credito.""",
    "confirmacion_reunion": """\
El objetivo unico de esta llamada es confirmar la reunion agendada con el ejecutivo. \
Confirma fecha y hora en palabras. Si no le acomoda, ofrece reagendar con dos alternativas concretas. \
No re califiques al lead ni abras temas nuevos. La llamada debe durar menos de dos minutos.""",
    "confirmacion_visita": """\
El objetivo unico de esta llamada es confirmar la visita a la propiedad que quedo agendada. \
Confirma fecha y hora en palabras y que sepa como llegar. Si no le acomoda, ofrece reagendar con dos alternativas concretas. \
No re califiques al lead ni abras temas nuevos. La llamada debe durar menos de dos minutos.""",
    "seguimiento_post_visita": """\
El objetivo de esta llamada es el seguimiento despues de la visita a la propiedad. \
Pregunta que le parecio, si sigue interesado, que objeciones tiene y cuales serian los proximos pasos. \
Escucha mas de lo que hablas. Si detectas alto interes, propone el siguiente paso concreto.""",
    "reactivacion": """\
El objetivo de esta llamada es reactivar a un lead que dejo de responder. \
Se breve y calido, recuerda el interes que mostro antes y pregunta si sigue buscando propiedad. \
Si su contexto cambio, registralo. Si no esta interesado, agradece y cierra sin insistir.""",
}

# Greeting bodies — get_purpose_greeting prepends "Hola" + optional lead name.
PURPOSE_GREETINGS = {
    "calificacion_inicial": (
        "te llamo del equipo comercial por tu interes en nuestras propiedades. "
        "Te pillo en un buen momento para conversar un par de minutos?"
    ),
    "calificacion_financiera": (
        "te llamo para avanzar con tu busqueda de propiedad. "
        "Quiero hacerte un par de preguntas rapidas para poder ayudarte mejor, te parece?"
    ),
    "confirmacion_reunion": (
        "te llamo para confirmar la reunion que tenemos agendada con nuestro ejecutivo. "
        "Te acomoda todavia el horario que coordinamos?"
    ),
    "confirmacion_visita": (
        "te llamo para confirmar la visita a la propiedad que tenemos agendada. "
        "Te acomoda todavia la fecha y hora que coordinamos?"
    ),
    "seguimiento_post_visita": (
        "te llamo para saber que te parecio la visita a la propiedad. "
        "Tienes un minuto para contarme?"
    ),
    "reactivacion": (
        "hace un tiempo conversamos sobre tu busqueda de propiedad y queria saber como vas. "
        "Sigues buscando?"
    ),
}


def get_purpose_instructions(purpose: Optional[str]) -> str:
    """Return the objective block for a call purpose, or empty string."""
    if not purpose:
        return ""
    return PURPOSE_INSTRUCTIONS.get(purpose, "")


def get_purpose_greeting(purpose: Optional[str], lead_name: str = "") -> Optional[str]:
    """Return the purpose-specific greeting (with lead name when known), or None."""
    if not purpose:
        return None
    body = PURPOSE_GREETINGS.get(purpose)
    if not body:
        return None
    prefix = f"Hola{', ' + lead_name if lead_name else ''}, soy Sofia, "
    return prefix + body
