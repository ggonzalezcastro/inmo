# Refactor: Mensajes Estructurados - Instrucciones

## ✅ Cambios Completados

1. **lead_context_service.py** - Ahora devuelve `message_history` como array estructurado

## ⚠️ Cambios Pendientes (Manuales)

### 1. llm_service.py - Función `build_llm_prompt`

**Línea 478-512:** Reemplazar completamente la función con:

```python
@staticmethod
async def build_llm_prompt(
    lead_context: Dict,
    new_message: str,
    db: Optional[AsyncSession] = None,
    broker_id: Optional[int] = None
) -> Tuple[str, List[types.Content]]:
    """
    Build LLM prompt with lead context, optionally using broker configuration.
    Returns (system_prompt, message_history) for structured API usage.
    
    Args:
        lead_context: Lead context dictionary with message_history as structured array
        new_message: New message from user
        db: Optional database session
        broker_id: Optional broker ID for configuration
        
    Returns:
        Tuple of (system_prompt, contents_list) where contents_list is ready for Gemini API
    """
    
    # Get system prompt from broker config or default
    system_prompt = None
    if broker_id and db:
        try:
            from app.services.broker_config_service import BrokerConfigService
            system_prompt = await BrokerConfigService.build_system_prompt(
                db, broker_id, lead_context
            )
        except Exception as e:
            if db:
                await db.rollback()
            logger.warning(f"Could not load broker config for broker_id {broker_id}: {e}")
    
    # Fallback to default if broker config not available
    if not system_prompt:
        from app.services.broker_config_service import BrokerConfigService
        system_prompt = BrokerConfigService.DEFAULT_SYSTEM_PROMPT
    
    # Get message history - prefer structured format, fallback to legacy
    message_history = lead_context.get('message_history', [])
    if isinstance(message_history, str):
        # Legacy format - convert to structured
        logger.warning("[LLM] Using legacy message_history format, converting...")
        message_history = []
        legacy_str = lead_context.get('message_history_legacy', '')
        if legacy_str:
            parts = legacy_str.split('|')
            for part in parts:
                if ':' in part:
                    prefix, content = part.split(':', 1)
                    role = "user" if prefix == "U" else "assistant"
                    message_history.append({"role": role, "content": content})
    
    # Build structured contents for Gemini API
    contents = []
    
    # Add conversation history (structured messages)
    for msg in message_history:
        role = msg.get("role", "user")
        content_text = msg.get("content", "")
        
        # Map roles: user -> "user", assistant -> "model" (Gemini format)
        gemini_role = "user" if role == "user" else "model"
        contents.append(types.Content(
            role=gemini_role,
            parts=[types.Part(text=content_text)]
        ))
    
    # Add new message from user
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=new_message)]
    ))
    
    # Add context summary as a final system instruction
    context_summary = LLMService._build_context_summary(lead_context, new_message)
    
    # Enhance system prompt with context summary
    enhanced_system_prompt = f"{system_prompt}\n\n{context_summary}"
    
    return enhanced_system_prompt, contents
```

### 2. llm_service.py - Función `_build_context_summary`

**Línea 613:** Cambiar:
```python
message_history = lead_context.get('message_history', '')
```

**A:**
```python
message_history = lead_context.get('message_history', [])
```

**Líneas 629-645:** Reemplazar el bloque completo que parsea message_history con:

```python
# Format message history in a more readable way for the LLM
if message_history:
    # Handle both structured format (list of dicts) and legacy format (string)
    if isinstance(message_history, list):
        # Structured format
        formatted_history = []
        for msg in message_history[-10:]:  # Last 10 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                formatted_history.append(f"  👤 Usuario: {content}")
            else:
                formatted_history.append(f"  🤖 Bot (TÚ): {content}")
        history_text = "\n".join(formatted_history) if formatted_history else "No hay historial previo"
    elif isinstance(message_history, str):
        # Legacy TOON format - parse and display nicely
        messages = message_history.split('|')
        formatted_history = []
        for msg in messages:
            if ':' in msg:
                prefix, content = msg.split(':', 1)
                if prefix == 'U':
                    formatted_history.append(f"  👤 Usuario: {content}")
                elif prefix == 'B':
                    formatted_history.append(f"  🤖 Bot (TÚ): {content}")
                else:
                    formatted_history.append(f"  {content}")
        history_text = "\n".join(formatted_history) if formatted_history else "No hay historial previo"
    else:
        history_text = "No hay historial previo"
else:
    history_text = "No hay historial previo"
```

### 3. llm_service.py - Función `generate_response_with_function_calling`

**Línea 303:** Cambiar la firma para aceptar system_prompt y contents separados:

```python
@staticmethod
async def generate_response_with_function_calling(
    system_prompt: str,
    contents: List[types.Content],
    tools: List[types.Tool],
    tool_executor: Optional[Callable] = None
) -> Tuple[str, List[Dict[str, Any]]]:
```

**Líneas 339-340:** Cambiar:
```python
contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
```

**A:**
```python
# Use the provided contents (already structured)
# Add system instruction separately
```

**Líneas 350-355:** Actualizar la llamada a la API:

```python
response = client.models.generate_content(
    model=settings.GEMINI_MODEL,
    contents=contents,
    config=config,
    system_instruction=system_prompt  # Add system prompt separately
)
```

### 4. routes/chat.py - Actualizar llamadas

**Línea 228-233:** Cambiar:
```python
prompt = await LLMService.build_llm_prompt(
    context, 
    chat_message.message,
    db=db,
    broker_id=broker_id
)
```

**A:**
```python
system_prompt, contents = await LLMService.build_llm_prompt(
    context, 
    chat_message.message,
    db=db,
    broker_id=broker_id
)
```

**Línea 263-267:** Cambiar:
```python
ai_response, function_calls = await LLMService.generate_response_with_function_calling(
    prompt=prompt,
    tools=tools,
    tool_executor=tool_executor
)
```

**A:**
```python
ai_response, function_calls = await LLMService.generate_response_with_function_calling(
    system_prompt=system_prompt,
    contents=contents,
    tools=tools,
    tool_executor=tool_executor
)
```

### 5. tasks/telegram_tasks.py - Actualizar llamadas

Similar a chat.py, actualizar las llamadas a `build_llm_prompt` y `generate_response_with_function_calling`.

## 🎯 Resultado Esperado

- ✅ Mensajes en formato estructurado estándar (role/content)
- ✅ Mejor comprensión del contexto por parte del LLM
- ✅ Menos preguntas repetidas
- ✅ Mejor manejo del estado de la conversación
