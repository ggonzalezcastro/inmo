"""
Pipeline stage constants shared by advancement and metrics services.
"""
PIPELINE_STAGES = {
    "entrada": "Lead inicial - recién recibido",
    "perfilamiento": "Recopilando información del cliente",
    "calificacion_financiera": "Validando capacidad financiera",
    "potencial": "Lead con potencial - requiere seguimiento comercial",
    "agendado": "Cita agendada",
    "ganado": "Cliente convertido",
    "perdido": "Oportunidad perdida",
}
