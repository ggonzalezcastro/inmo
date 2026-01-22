from google import genai
from google.genai import types
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Ensure INFO level logging


# Configure Gemini client
client = None
if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "":
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    logger.info(f"Gemini client configured with model: {settings.GEMINI_MODEL}")
else:
    logger.warning("Gemini API key not configured")


class LLMService:
    """Service for Google Gemini API integration"""
    
    FALLBACK_RESPONSE = "Gracias por tu mensaje. Un agente estará contigo pronto para ayudarte."
    
    @staticmethod
    async def generate_response(prompt: str) -> str:
        """Generate response from Gemini"""
        
        logger.info(f"[LLM] generate_response called - Prompt length: {len(prompt)} chars")
        
        # Check if API key is configured
        if not client:
            logger.warning("[LLM] Gemini client not configured, using fallback response")
            return LLMService.FALLBACK_RESPONSE
        
        logger.info(f"[LLM] Using model: {settings.GEMINI_MODEL}")
        logger.debug(f"[LLM] Prompt preview: {prompt[:200]}...")
        
        try:
            # Generate content using new API
            logger.info("[LLM] Calling Gemini API...")
            logger.debug(f"[LLM] Prompt being sent (first 500 chars): {prompt[:500]}...")
            logger.info(f"[LLM] Prompt total length: {len(prompt)} chars")
            
            start_time = time.time()
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
            )
            elapsed_time = time.time() - start_time
            
            response_text = response.text.strip()
            logger.info(f"[LLM] ⏱️  Gemini API response time: {elapsed_time:.2f} seconds")
            logger.info(f"[LLM] Response received from Gemini API - Length: {len(response_text)} chars")
            logger.info(f"[LLM] Full response text: '{response_text}'")
            logger.debug(f"[LLM] Response type: {type(response).__name__}")
            
            # Clean response - remove any prompt context that might have been included
            # Split by "RESPUESTA" or "R:" and take only the last part
            if "RESPUESTA" in response_text:
                response_text = response_text.split("RESPUESTA")[-1].strip()
                if response_text.startswith(":"):
                    response_text = response_text[1:].strip()
            elif "R:" in response_text and response_text.count("R:") > 1:
                # Multiple R: markers, take content after last one
                parts = response_text.split("R:")
                if len(parts) > 1:
                    response_text = parts[-1].strip()
            
            # Remove any remaining context markers
            lines = response_text.split('\n')
            cleaned_lines = []
            skip_until_response = False
            for line in lines:
                # Skip context lines (P:, INFO_OK:, H:, M:)
                if line.startswith(('P:', 'INFO_OK:', 'H:', 'M:')):
                    continue
                # If we see "R:" or "RESPUESTA", start collecting from next line
                if 'R:' in line or 'RESPUESTA' in line:
                    skip_until_response = True
                    # Take content after R: if present
                    if 'R:' in line:
                        after_r = line.split('R:')[-1].strip()
                        if after_r:
                            cleaned_lines.append(after_r)
                    continue
                # Collect all other lines
                if not skip_until_response or line.strip():
                    cleaned_lines.append(line)
            
            response_text = '\n'.join(cleaned_lines).strip()
            
            # If response is empty or too short, return fallback
            if not response_text or len(response_text) < 5:
                logger.warning("[LLM] Response too short or empty, using fallback")
                return LLMService.FALLBACK_RESPONSE
            
            logger.info(f"[LLM] Cleaned response - Length: {len(response_text)} chars")
            return response_text
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[LLM] Gemini error in generate_response: {error_msg}", exc_info=True)
            logger.error(f"[LLM] Error type: {type(e).__name__}")
            
            # Check if it's a quota/rate limit error
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                logger.warning("[LLM] Gemini API quota exceeded - using fallback response")
                # Return a more informative fallback message when quota is exceeded
                return "Lo siento, estoy experimentando problemas técnicos temporales. Por favor, intenta de nuevo en unos momentos o contacta directamente con un agente."
            
            # Check if it's a service unavailable error (503)
            if "503" in error_msg or "UNAVAILABLE" in error_msg or "overloaded" in error_msg.lower():
                logger.warning("[LLM] Gemini API service unavailable (overloaded) - using fallback response")
                return "El servicio está temporalmente sobrecargado. Por favor, intenta de nuevo en unos momentos o contacta directamente con un agente."
            
            return LLMService.FALLBACK_RESPONSE
    
    @staticmethod
    async def analyze_lead_qualification(message: str, lead_context: Dict = None) -> Dict[str, Any]:
        """Analyze message to qualify lead and extract data"""
        
        logger.info(f"[LLM] analyze_lead_qualification called - Message: {message[:100]}...")
        
        # Check if API key is configured
        if not client:
            logger.warning("[LLM] Gemini client not configured, returning default analysis")
            return {
                "qualified": "maybe",
                "interest_level": 5,
                "budget": None,
                "timeline": "unknown",
                "name": None,
                "phone": None,
                "email": None,
                "salary": None,
                "location": None,
                "dicom_status": None,
                "morosidad_amount": None,
                "key_points": [],
                "score_delta": 0
            }
        
        # Build context information about existing lead data
        existing_data = ""
        if lead_context:
            if lead_context.get("name"):
                existing_data += f"Ya tenemos nombre: {lead_context.get('name')}\n"
            if lead_context.get("phone") and not str(lead_context.get("phone", "")).startswith("web_chat_") and not str(lead_context.get("phone", "")).startswith("whatsapp_"):
                existing_data += f"Ya tenemos teléfono: {lead_context.get('phone')}\n"
            if lead_context.get("email"):
                existing_data += f"Ya tenemos email: {lead_context.get('email')}\n"
            metadata = lead_context.get("metadata", {})
            # NO mostrar presupuesto - solo renta/sueldo
            if metadata.get("monthly_income") or metadata.get("salary"):
                income = metadata.get("monthly_income") or metadata.get("salary")
                existing_data += f"Ya tenemos renta/sueldo: {income}\n"
            if metadata.get("location"):
                existing_data += f"Ya tenemos ubicación: {metadata.get('location')}\n"
        
        context_note = f"\n\nDatos existentes del lead:\n{existing_data}" if existing_data else "\n\nNo hay datos previos del lead."
        
        # Extract last bot message for context from message_history (format U:msg|B:msg)
        last_bot_message = ""
        if lead_context and lead_context.get("message_history"):
            try:
                history_str = lead_context.get("message_history", "")
                parts = history_str.split("|")
                for part in reversed(parts):
                    if part.startswith("B:"):
                        last_bot_message = part[2:]
                        break
            except Exception:
                pass
            
        context_context = f"\nPREGUNTA ANTERIOR DEL ASISTENTE: \"{last_bot_message}\"\n\nIMPORTANTE: Usa esta pregunta anterior para interpretar correctamente la respuesta del usuario." if last_bot_message else ""
        
        analysis_prompt = f"""Analiza este mensaje y extrae SOLO los datos nuevos mencionados. Mensaje: "{message}"
{context_note}
{context_context}

IMPORTANTE:
1. Solo extrae datos que se mencionan en este mensaje. Si un dato ya existe en el lead, no lo incluyas en la respuesta (pon null).
2. USA LA "PREGUNTA ANTERIOR DEL ASISTENTE" PARA INTERPRETAR LA RESPUESTA:
   - Si preguntó por DICOM/deudas y responde "no" → dicom_status="clean", morosidad_amount=null (NO tiene deudas)
   - Si preguntó por DICOM/deudas y responde "sí" → dicom_status="has_debt" (tiene deudas, preguntar monto después)
   - Si preguntó por "renta", "sueldo", "ingresos", "renta líquida" y responde número o texto numérico → salary (NO es morosidad_amount)
   - SI LA PREGUNTA ANTERIOR ERA SOBRE RENTA/SUELDO Y RESPONDEN CON NÚMERO → SIEMPRE ES salary, NUNCA budget, NUNCA morosidad_amount
   - Ejemplos: "2 millones" después de preguntar renta = 2000000 → salary, "1500000" = 1500000 → salary
   - ⚠️ CRÍTICO: NO confundas salary con morosidad_amount. Si el contexto muestra dicom_status="clean", entonces morosidad_amount DEBE ser null.
3. NO EXTRAGAS 'budget' (PRESUPUESTO) A MENOS QUE EXPLÍCITAMENTE MENCIONEN "presupuesto", "precio del inmueble", "valor máximo"
   - Si solo mencionan un número después de preguntar por renta → SIEMPRE es salary
   - Palabras clave Salary: "sueldo", "gano", "renta", "ingresos", "liquido", "mensual".
   - NO uses budget a menos que el usuario explícitamente diga "presupuesto para comprar" o "precio máximo"

Retorna JSON con:
- qualified: "yes"/"no"/"maybe"
- interest_level: 1-10
- budget: monto en UF/CLP si menciona PRESUPUESTO en ESTE mensaje, sino null
- timeline: "immediate"/"30days"/"90days"/"unknown"
- name: nombre completo si menciona en ESTE mensaje, sino null
- phone: teléfono si menciona en ESTE mensaje, sino null
- email: email si menciona en ESTE mensaje, sino null
- salary: monto de SUELDO/RENTA si menciona en ESTE mensaje, sino null
- location: ubicación (comuna/sector) si menciona en ESTE mensaje, sino null
- dicom_status: "clean" (si dice NO tengo dicom/deuda), "has_debt" (si dice SI tiene), "unknown" (si no sabe)
- morosidad_amount: monto de la deuda si lo menciona, sino null
- key_points: lista de puntos importantes del mensaje
- score_delta: -10 a +20

Ejemplos con contexto:
1. Pregunta anterior: "¿Cuál es tu renta líquida mensual aproximada?"
   Mensaje: "1.500.000"
   Respuesta CORRECTA: {{"salary": 1500000, "budget": null, "score_delta": 10, ...}}

2. Pregunta anterior: "¿Actualmente estás en DICOM o tienes deudas morosas?"
   Mensaje: "no"
   Respuesta CORRECTA: {{"dicom_status": "clean", "score_delta": 5, "key_points": ["Cliente confirma no estar en DICOM"], ...}}

3. Pregunta anterior: "¿Me podrías dar tu número de teléfono?"
   Mensaje: "no"
   Respuesta CORRECTA: {{"score_delta": -10, "key_points": ["Cliente rechaza dar teléfono"], ...}}

Solo JSON válido."""
        
        logger.info(f"[LLM] Analysis prompt length: {len(analysis_prompt)} chars")
        logger.debug(f"[LLM] Analysis prompt: {analysis_prompt[:300]}...")
        
        try:
            # Generate content using new API
            logger.info("[LLM] Calling Gemini API for analysis...")
            logger.debug(f"[LLM] Analysis prompt (first 500 chars): {analysis_prompt[:500]}...")
            logger.info(f"[LLM] Analysis prompt total length: {len(analysis_prompt)} chars")
            
            start_time = time.time()
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=analysis_prompt,
            )
            elapsed_time = time.time() - start_time
            
            response_text = response.text.strip()
            logger.info(f"[LLM] ⏱️  Gemini API analysis response time: {elapsed_time:.2f} seconds")
            logger.info(f"[LLM] Analysis response received - Length: {len(response_text)} chars")
            logger.info(f"[LLM] Full analysis response: '{response_text}'")
            logger.debug(f"[LLM] Response type: {type(response).__name__}")
            
            # Clean response - remove markdown code blocks if present
            if response_text.startswith("```"):
                # Remove ```json or ``` markers
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
                logger.debug(f"[LLM] Cleaned response: {response_text}")
            
            # Parse JSON response
            logger.debug("[LLM] Parsing JSON response...")
            analysis = json.loads(response_text)
            logger.info(f"[LLM] Analysis parsed successfully: {analysis}")
            logger.debug(f"[LLM] Analysis keys: {list(analysis.keys())}")
            logger.debug(f"[LLM] Qualified: {analysis.get('qualified')}, Interest level: {analysis.get('interest_level')}, Score delta: {analysis.get('score_delta')}")
            
            return {
                "qualified": analysis.get("qualified", "maybe"),
                "interest_level": analysis.get("interest_level", 5),
                "budget": analysis.get("budget"),
                "timeline": analysis.get("timeline", "unknown"),
                "name": analysis.get("name"),
                "phone": analysis.get("phone"),
                "email": analysis.get("email"),
                "salary": analysis.get("salary"),
                "location": analysis.get("location"),
                "dicom_status": analysis.get("dicom_status"),
                "morosidad_amount": analysis.get("morosidad_amount"),
                "key_points": analysis.get("key_points", []),
                "score_delta": analysis.get("score_delta", 0)
            }
        
        except json.JSONDecodeError as e:
            logger.warning(f"[LLM] Failed to parse Gemini response as JSON: {str(e)}")
            logger.warning(f"[LLM] Response text: {response_text if 'response_text' in locals() else 'N/A'}")
            return {
                "qualified": "maybe",
                "interest_level": 5,
                "budget": None,
                "timeline": "unknown",
                "name": None,
                "phone": None,
                "email": None,
                "salary": None,
                "location": None,
                "dicom_status": None,
                "morosidad_amount": None,
                "key_points": [],
                "score_delta": 0
            }
        except Exception as e:
            logger.error(f"[LLM] Gemini analysis error: {str(e)}", exc_info=True)
            logger.error(f"[LLM] Error type: {type(e).__name__}")
            return {
                "qualified": "maybe",
                "interest_level": 5,
                "budget": None,
                "timeline": "unknown",
                "name": None,
                "phone": None,
                "email": None,
                "salary": None,
                "location": None,
                "dicom_status": None,
                "morosidad_amount": None,
                "key_points": [],
                "score_delta": 0
            }
    
    @staticmethod
    async def generate_response_with_function_calling(
        system_prompt: str,
        contents: List[types.Content],
        tools: List[types.Tool],
        tool_executor: Optional[Callable] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generate response with manual function calling handling
        This allows us to execute functions ourselves and send results back
        
        Args:
            system_prompt: The system prompt/instruction for the model
            contents: List of Content objects (structured messages) for conversation history
            tools: List of Tool objects with function declarations
            tool_executor: Optional async function to execute tools (name, args) -> result
        
        Returns:
            Tuple of (final_response_text, function_calls_executed)
        """
        
        logger.info(f"[LLM] generate_response_with_function_calling called")
        logger.info(f"[LLM] System prompt length: {len(system_prompt)} chars")
        logger.info(f"[LLM] Contents count: {len(contents)} messages")
        logger.info(f"[LLM] Tools count: {len(tools)} tools")
        
        if not client:
            logger.warning("[LLM] Gemini client not configured")
            return LLMService.FALLBACK_RESPONSE, []
        
        try:
            from google.genai import types
            
            # Configure with tools but disable automatic execution
            # Note: system_instruction might not be supported in this version of the API
            # We'll prepend it to contents instead
            logger.debug("[LLM] Configuring GenerateContentConfig with tools")
            logger.info(f"[LLM] Config: max_output_tokens={settings.GEMINI_MAX_TOKENS}, temperature={settings.GEMINI_TEMPERATURE}")
            config = types.GenerateContentConfig(
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True  # We'll handle function calling manually
                ),
                # Limit output tokens for faster responses
                max_output_tokens=settings.GEMINI_MAX_TOKENS,
                temperature=settings.GEMINI_TEMPERATURE
            )
            
            # Prepend system instruction as first content in the conversation
            # Some Gemini API versions don't support system_instruction parameter
            logger.debug("[LLM] Prepending system instruction to contents")
            contents_with_system = [
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"INSTRUCCIONES DEL SISTEMA:\n{system_prompt}\n\n---\n\nCONTINÚA LA CONVERSACIÓN:")]
                )
            ] + contents
            logger.info(f"[LLM] Contents with system - Total count: {len(contents_with_system)} messages")
            logger.debug(f"[LLM] System instruction preview: {system_prompt[:200]}...")
            
            # Use the provided contents (already structured)
            
            function_calls_executed = []
            max_iterations = 5
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"[LLM] Function calling iteration {iteration}/{max_iterations}")
                
                # Send request with system instruction prepended to contents
                current_contents = contents_with_system if iteration == 1 else contents
                total_chars = sum(len(c.parts[0].text) if c.parts else 0 for c in current_contents)
                logger.info(f"[LLM] Sending request to Gemini API - Model: {settings.GEMINI_MODEL}, Contents: {len(current_contents)} messages, Total chars: {total_chars}")
                logger.debug(f"[LLM] Last message in contents: {current_contents[-1].parts[0].text[:100] if current_contents and current_contents[-1].parts else 'N/A'}...")
                
                start_time = time.time()
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=current_contents,  # Only prepend system on first iteration
                    config=config
                )
                elapsed_time = time.time() - start_time
                
                logger.info(f"[LLM] ⏱️  Gemini API response time (iteration {iteration}): {elapsed_time:.2f} seconds")
                logger.info(f"[LLM] Response received from Gemini API")
                logger.debug(f"[LLM] Response type: {type(response).__name__}, Has candidates: {hasattr(response, 'candidates')}")
                
                # Check for function calls in response
                function_calls_in_response = []
                text_response = None
                
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            # Check for function call
                            if hasattr(part, 'function_call') and part.function_call:
                                func_call = part.function_call
                                func_name = func_call.name if hasattr(func_call, 'name') else None
                                func_args = dict(func_call.args) if hasattr(func_call, 'args') else {}
                                
                                if func_name:
                                    function_calls_in_response.append({
                                        "name": func_name,
                                        "args": func_args
                                    })
                            
                            # Check for text response
                            if hasattr(part, 'text') and part.text and part.text.strip():
                                text_response = part.text.strip()
                
                # If no function calls, return text response
                if not function_calls_in_response:
                    if text_response:
                        logger.info(f"[LLM] Final response received: {len(text_response)} chars")
                        logger.info(f"[LLM] Final response text: '{text_response}'")
                        logger.debug(f"[LLM] Function calls executed during conversation: {len(function_calls_executed)}")
                        return text_response, function_calls_executed
                    elif hasattr(response, 'text') and response.text:
                        return response.text.strip(), function_calls_executed
                    else:
                        logger.warning("[LLM] No function calls and no text response")
                        return LLMService.FALLBACK_RESPONSE, function_calls_executed
                
                # Execute function calls
                function_results = []
                for func_call in function_calls_in_response:
                    func_name = func_call["name"]
                    func_args = func_call["args"]
                    
                    logger.info(f"[LLM] Executing function: {func_name} with args: {func_args}")
                    
                    # Execute function if executor provided
                    if tool_executor:
                        try:
                            logger.debug(f"[LLM] Calling tool_executor for {func_name}")
                            func_result = await tool_executor(func_name, func_args)
                            logger.info(f"[LLM] Function {func_name} executed successfully")
                            logger.debug(f"[LLM] Function {func_name} result: {func_result}")
                            function_calls_executed.append({
                                "name": func_name,
                                "args": func_args,
                                "result": func_result
                            })
                            function_results.append(types.FunctionResponse(
                                name=func_name,
                                response=func_result
                            ))
                        except Exception as e:
                            logger.error(f"[LLM] Error executing function {func_name}: {str(e)}", exc_info=True)
                            error_result = {"success": False, "error": str(e)}
                            function_calls_executed.append({
                                "name": func_name,
                                "args": func_args,
                                "result": error_result
                            })
                            function_results.append(types.FunctionResponse(
                                name=func_name,
                                response=error_result
                            ))
                    else:
                        # No executor, just log
                        logger.warning(f"[LLM] No tool executor provided for {func_name}")
                
                # Add function results to conversation
                if function_results:
                    # Add assistant's function call to conversation
                    function_call_parts = [
                        types.Part(function_call=types.FunctionCall(
                            name=fc["name"],
                            args=fc["args"]
                        ))
                        for fc in function_calls_in_response
                    ]
                    contents.append(types.Content(
                        role="model",
                        parts=function_call_parts
                    ))
                    
                    # Add function results
                    contents.append(types.Content(
                        role="user",
                        parts=[
                            types.Part(function_response=fr) 
                            for fr in function_results
                        ]
                    ))
                else:
                    # No results, break
                    break
            
            # Max iterations reached
            logger.warning(f"[LLM] Max iterations ({max_iterations}) reached")
            return LLMService.FALLBACK_RESPONSE, function_calls_executed
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[LLM] Error in generate_response_with_function_calling: {error_msg}", exc_info=True)
            
            # Check if it's a quota/rate limit error
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                logger.warning("[LLM] Gemini API quota exceeded in function calling - using informative fallback")
                quota_message = "Lo siento, estoy experimentando problemas técnicos temporales. Por favor, intenta de nuevo en unos momentos o contacta directamente con un agente."
                return quota_message, []
            
            # Check if it's a service unavailable error (503)
            if "503" in error_msg or "UNAVAILABLE" in error_msg or "overloaded" in error_msg.lower():
                logger.warning("[LLM] Gemini API service unavailable (overloaded) - using informative fallback")
                unavailable_message = "El servicio está temporalmente sobrecargado. Por favor, intenta de nuevo en unos momentos o contacta directamente con un agente."
                return unavailable_message, []
            
            return LLMService.FALLBACK_RESPONSE, []
    
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
        
        logger.info(f"[LLM] ========== build_llm_prompt STARTED ==========")
        logger.info(f"[LLM] New message: '{new_message[:100]}...'")
        logger.info(f"[LLM] Broker ID: {broker_id}")
        logger.info(f"[LLM] Lead context keys: {list(lead_context.keys())}")
        
        # Get system prompt from broker config or default
        system_prompt = None
        if broker_id and db:
            try:
                logger.info(f"[LLM] Loading broker config for broker_id: {broker_id}")
                from app.services.broker_config_service import BrokerConfigService
                system_prompt = await BrokerConfigService.build_system_prompt(
                    db, broker_id, lead_context
                )
                logger.info(f"[LLM] Broker config loaded - System prompt length: {len(system_prompt)} chars")
            except Exception as e:
                if db:
                    await db.rollback()
                logger.warning(f"[LLM] Could not load broker config for broker_id {broker_id}: {e}")
        
        # Fallback to default if broker config not available
        if not system_prompt:
            logger.info("[LLM] Using DEFAULT_SYSTEM_PROMPT (no broker config available)")
            from app.services.broker_config_service import BrokerConfigService
            system_prompt = BrokerConfigService.DEFAULT_SYSTEM_PROMPT
        
        logger.debug(f"[LLM] System prompt preview (first 300 chars): {system_prompt[:300]}...")
        
        # Get message history - prefer structured format, fallback to legacy
        message_history = lead_context.get('message_history', [])
        logger.info(f"[LLM] Message history type: {type(message_history).__name__}, length: {len(message_history) if isinstance(message_history, list) else 'N/A'}")
        
        if isinstance(message_history, str):
            # Legacy format - convert to structured
            logger.warning("[LLM] Using legacy message_history format, converting...")
            message_history = []
            legacy_str = lead_context.get('message_history_legacy', '')
            if legacy_str:
                parts = legacy_str.split('|')
                logger.debug(f"[LLM] Converting {len(parts)} legacy message parts")
                for part in parts:
                    if ':' in part:
                        prefix, content = part.split(':', 1)
                        role = "user" if prefix == "U" else "assistant"
                        message_history.append({"role": role, "content": content})
        
        # Build structured contents for Gemini API
        contents = []
        
        # Add conversation history (structured messages)
        logger.info(f"[LLM] Building structured contents from {len(message_history)} message(s)")
        for idx, msg in enumerate(message_history):
            role = msg.get("role", "user")
            content_text = msg.get("content", "")
            
            # Map roles: user -> "user", assistant -> "model" (Gemini format)
            gemini_role = "user" if role == "user" else "model"
            contents.append(types.Content(
                role=gemini_role,
                parts=[types.Part(text=content_text)]
            ))
            logger.debug(f"[LLM] Added message {idx+1}: role={gemini_role}, content_length={len(content_text)}, preview: '{content_text[:50]}...'")
        
        # Add new message from user
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=new_message)]
        ))
        logger.info(f"[LLM] Added new user message - Length: {len(new_message)} chars")
        logger.debug(f"[LLM] New message content: '{new_message}'")
        
        # Add context summary as a final system instruction
        logger.info("[LLM] Building context summary...")
        context_summary = LLMService._build_context_summary(lead_context, new_message)
        logger.info(f"[LLM] Context summary built - Length: {len(context_summary)} chars")
        logger.info(f"[LLM] Context summary preview (first 500 chars):\n{context_summary[:500]}...")
        logger.debug(f"[LLM] Context summary full content:\n{context_summary}")
        
        # Enhance system prompt with context summary
        enhanced_system_prompt = f"{system_prompt}\n\n{context_summary}"
        logger.info(f"[LLM] Enhanced system prompt - Total length: {len(enhanced_system_prompt)} chars")
        logger.info(f"[LLM] Total contents count: {len(contents)} messages")
        logger.info(f"[LLM] ========== build_llm_prompt COMPLETED ==========")
        logger.debug(f"[LLM] Enhanced system prompt full content:\n{enhanced_system_prompt[:1000]}...")
        
        return enhanced_system_prompt, contents
    
    @staticmethod
    def _build_context_summary(lead_context: Dict, new_message: str = "") -> str:
        """Build context summary from lead context"""
        logger.debug("[LLM] _build_context_summary called")
        metadata = lead_context.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
            logger.debug("[LLM] Metadata was not a dict, using empty dict")
        
        # Get actual values
        lead_name = lead_context.get('name', 'User')
        lead_phone = lead_context.get('phone')
        lead_email = lead_context.get('email')
        location = metadata.get('location') if metadata else None
        salary = metadata.get('salary') if metadata else None
        monthly_income = metadata.get('monthly_income') if metadata else None
        
        # Determine what we have
        has_name = lead_name and lead_name not in ['User', 'Test User']
        has_phone = (
            lead_phone is not None 
            and lead_phone != '-' 
            and not str(lead_phone).startswith('web_chat_')
            and not str(lead_phone).startswith('whatsapp_')
            and not str(lead_phone).startswith('+569999')
        )
        has_email = lead_email is not None and lead_email.strip() != ''
        has_location = location is not None and str(location).strip() != ''
        # Check for salary/income (don't check for budget)
        has_salary = (salary is not None and str(salary).strip() != '') or (monthly_income is not None and str(monthly_income).strip() != '')
        
        # Build info display
        info_collected = []
        if has_name:
            info_collected.append(f"NOMBRE: {lead_name}")
        if has_phone:
            info_collected.append(f"TELÉFONO: {lead_phone}")
        if has_email:
            info_collected.append(f"EMAIL: {lead_email}")
        if has_location:
            info_collected.append(f"UBICACIÓN: {location}")
        # NO mostrar presupuesto - solo renta/sueldo
        if has_salary:
            income_value = monthly_income or salary
            if isinstance(income_value, (int, float)):
                info_collected.append(f"RENTA/SUELDO: ${income_value:,}")
            else:
                info_collected.append(f"RENTA/SUELDO: {income_value}")
        
        # Nuevos campos financieros
        monthly_income = metadata.get("monthly_income")
        if monthly_income:
            try:
                income_value = int(monthly_income)
                info_collected.append(f"INGRESOS: ${income_value:,}")
            except (ValueError, TypeError):
                info_collected.append(f"INGRESOS: {monthly_income}")
        
        dicom_status = metadata.get("dicom_status")
        if dicom_status:
            status_text = {
                "clean": "✅ Limpio (NO está en DICOM - EXCELENTE SEÑAL, CONTINUAR CALIFICACIÓN)",
                "has_debt": "⚠️ Con deuda",
                "unknown": "❓ Desconocido"
            }.get(dicom_status, dicom_status)
            info_collected.append(f"DICOM: {status_text}")
            
            # SOLO mostrar morosidad si dicom_status es "has_debt"
            if dicom_status == "has_debt":
                morosidad_amount = metadata.get("morosidad_amount", 0)
                if morosidad_amount:
                    try:
                        morosidad = int(morosidad_amount)
                        if morosidad > 0:
                            info_collected.append(f"Deuda morosa: ${morosidad:,}")
                    except (ValueError, TypeError):
                        pass
        
        calificacion = metadata.get("calificacion")
        if calificacion:
            info_collected.append(f"CALIFICACIÓN: {calificacion}")
        
        # Show interest confirmation status
        interest_confirmed = metadata.get("interest_confirmed")
        if interest_confirmed:
            info_collected.append("✅ INTERÉS CONFIRMADO (usuario ya confirmó que está interesado)")
        
        info_needed = []
        if not has_name:
            info_needed.append("NOMBRE")
        if not has_phone:
            info_needed.append("TELÉFONO")
        if not has_email:
            info_needed.append("EMAIL (REQUERIDO para agendar reunión)")
        if not has_location:
            info_needed.append("UBICACIÓN")
        if not monthly_income and not has_salary:
            info_needed.append("RENTA/INGRESOS mensuales")
        if not dicom_status or dicom_status == "unknown":
            info_needed.append("SITUACIÓN DICOM")
        
        message_history = lead_context.get('message_history', [])
        
        # Build the summary
        summary_parts = []
        
        if info_collected:
            summary_parts.append(f"""✅ DATOS YA RECOPILADOS:
{chr(10).join(info_collected)}""")
        
        if info_needed:
            summary_parts.append(f"""⚠️ DATOS QUE AÚN FALTAN:
{", ".join(info_needed)}""")
        else:
            summary_parts.append("✅ TODOS LOS DATOS BÁSICOS RECOPILADOS")
        
        # Format message history in a more readable way for the LLM
        logger.debug(f"[LLM] Formatting message history - Type: {type(message_history).__name__}, Length: {len(message_history) if isinstance(message_history, (list, str)) else 'N/A'}")
        if message_history:
            # Handle both structured format (list of dicts) and legacy format (string)
            if isinstance(message_history, list):
                # Structured format
                logger.debug(f"[LLM] Processing structured message history - {len(message_history)} messages")
                formatted_history = []
                for msg in message_history[-10:]:  # Last 10 messages
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        formatted_history.append(f"  👤 Usuario: {content}")
                    else:
                        formatted_history.append(f"  🤖 Bot (TÚ): {content}")
                history_text = "\n".join(formatted_history) if formatted_history else "No hay historial previo"
                logger.debug(f"[LLM] Formatted history - {len(formatted_history)} messages formatted")
            elif isinstance(message_history, str):
                # Legacy TOON format - parse and display nicely
                logger.debug(f"[LLM] Processing legacy TOON format - String length: {len(message_history)}")
                messages = message_history.split('|')
                logger.debug(f"[LLM] Split into {len(messages)} parts")
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
                logger.debug(f"[LLM] Legacy format parsed - {len(formatted_history)} messages formatted")
            else:
                history_text = "No hay historial previo"
        else:
            history_text = "No hay historial previo"
        
        summary_parts.append(f"""HISTORIAL DE CONVERSACIÓN (últimos mensajes):
{history_text}

⚠️ CRÍTICO: Lee CUIDADOSAMENTE el historial arriba. NO preguntes algo que YA preguntaste antes.""")
        
        # Add explicit warning if interest was already confirmed
        if interest_confirmed:
            summary_parts.append("⚠️ IMPORTANTE: El usuario YA confirmó su interés. NO vuelvas a preguntarle si está interesado o si quiere agendar. Continúa directamente recopilando los datos que faltan o agendando si ya tienes todo.")
        
        summary = "\n\n".join(summary_parts)
        
        if new_message:
            summary += f"\n\nMENSAJE ACTUAL:\n{new_message}\n\nTU RESPUESTA (máximo 2 oraciones, NO pidas info ya recopilada, NO preguntes por interés si ya fue confirmado):"
        
        return summary