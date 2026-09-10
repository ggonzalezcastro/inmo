"""Pipeline stage names in a dependency-neutral module."""

PIPELINE_STAGE_ENTRY = "entrada"
PIPELINE_STAGE_WON = "ganado"

PIPELINE_STAGES = {
    PIPELINE_STAGE_ENTRY: "Lead inicial - recién recibido",
    "perfilamiento": "Recopilando información del cliente",
    "calificacion_financiera": "Validando capacidad financiera",
    "potencial": "Lead con potencial - requiere seguimiento comercial",
    "agendado": "Cita agendada",
    PIPELINE_STAGE_WON: "Cliente convertido",
    "perdido": "Oportunidad perdida",
}
