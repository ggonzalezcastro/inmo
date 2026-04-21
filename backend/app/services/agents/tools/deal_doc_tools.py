"""
LLM tool for inferring the document slot from a file name/type.
Used by the AI chat intake to classify documents received from leads.
"""
from app.services.llm.base_provider import LLMToolDefinition
from app.services.deals.slots import SLOT_DEFINITIONS, is_slot_key_valid

# Tool definition (used in LLM function calling)
INFER_DOC_SLOT_TOOL = LLMToolDefinition(
    name="infer_doc_slot",
    description=(
        "Infiere el tipo de documento a partir del nombre del archivo y contexto. "
        "Devuelve la clave del slot correspondiente del sistema de documentos de compraventa inmobiliaria. "
        "Usar cuando se recibe un archivo adjunto de un cliente y se necesita clasificarlo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "slot_key": {
                "type": "string",
                "enum": list(SLOT_DEFINITIONS.keys()),
                "description": "La clave del slot de documento más apropiada para el archivo"
            },
            "confidence": {
                "type": "string",
                "enum": ["alta", "media", "baja"],
                "description": "Confianza en la clasificación"
            },
            "reasoning": {
                "type": "string",
                "description": "Breve explicación de por qué se eligió este slot"
            }
        },
        "required": ["slot_key", "confidence"]
    }
)


async def infer_doc_slot_with_llm(
    filename: str,
    mime_type: str,
    extracted_text: str | None = None,
) -> str:
    """
    Use LLM function calling to infer the document slot from filename/content.
    Falls back to "sin_clasificar" on any error.

    Returns: slot_key string
    """
    from app.services.llm.facade import LLMServiceFacade
    from app.services.llm.base_provider import LLMMessage

    # Build slot descriptions for context
    slot_descriptions = "\n".join(
        f"- {key}: {defn.label}"
        for key, defn in SLOT_DEFINITIONS.items()
        if key != "sin_clasificar"
    )

    system_prompt = f"""Eres un asistente especializado en documentación inmobiliaria chilena.
Tu tarea es clasificar documentos recibidos de clientes en el proceso de compraventa.

Slots disponibles:
{slot_descriptions}

Clasifica el documento al slot más apropiado. Si no puedes determinar el tipo con razonable certeza, usa "sin_clasificar"."""

    user_content = f"Archivo: {filename}\nTipo MIME: {mime_type}"
    if extracted_text:
        user_content += f"\nTexto extraído (primeros 500 chars): {extracted_text[:500]}"

    inferred_slot = "sin_clasificar"

    def tool_executor(tool_name: str, tool_args: dict) -> str:
        nonlocal inferred_slot
        if tool_name == "infer_doc_slot":
            slot = tool_args.get("slot_key", "sin_clasificar")
            if is_slot_key_valid(slot):
                inferred_slot = slot
        return f"Slot clasificado: {inferred_slot}"

    try:
        await LLMServiceFacade.generate_response_with_function_calling(
            system_prompt=system_prompt,
            contents=[LLMMessage(role="user", content=user_content)],
            tools=[INFER_DOC_SLOT_TOOL],
            tool_executor=tool_executor,
            tool_mode_override="ANY",  # force function calling
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"LLM slot inference failed: {e}")

    return inferred_slot
