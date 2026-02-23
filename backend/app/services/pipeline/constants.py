"""
Pipeline stage constants shared by advancement and metrics services.
"""
PIPELINE_STAGES = {
    "entrada": "Lead inicial - recién recibido",
    "perfilamiento": "Recopilando información del cliente",
    "calificacion_financiera": "Validando capacidad financiera",
    "agendado": "Cita agendada",
    "seguimiento": "Seguimiento post-reunión",
    "referidos": "Esperando referidos",
    "ganado": "Cliente convertido",
    "perdido": "Oportunidad perdida",
}
