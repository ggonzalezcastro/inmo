"""
Google Gemini LLM Provider

Implements the BaseLLMProvider interface for Google Gemini API.
"""
import json
import time
import logging
from typing import Dict, Any, List, Tuple, Callable, Optional

from google import genai
from google.genai import types

from app.services.llm.base_provider import (
    BaseLLMProvider, 
    LLMMessage, 
    LLMToolCall,
    LLMToolDefinition,
    LLMResponse,
    MessageRole
)
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini LLM Provider implementation.
    
    Wraps the Google Generative AI SDK to provide a unified interface.
    """
    
    def __init__(
        self, 
        api_key: str = None, 
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
        **kwargs
    ):
        api_key = api_key or settings.GEMINI_API_KEY
        model = model or settings.GEMINI_MODEL
        super().__init__(api_key, model, **kwargs)
        
        self.max_tokens = max_tokens or settings.GEMINI_MAX_TOKENS
        self.temperature = temperature or settings.GEMINI_TEMPERATURE
        
        # Initialize client
        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"GeminiProvider initialized with model: {self.model}")
        else:
            logger.warning("GeminiProvider: No API key provided")
    
    @property
    def is_configured(self) -> bool:
        return bool(self._client and self.api_key)
    
    async def generate_response(self, prompt: str) -> str:
        """Generate simple text response from Gemini"""
        if not self.is_configured:
            logger.warning("[Gemini] Not configured, using fallback")
            return self.FALLBACK_RESPONSE
        
        try:
            start_time = time.time()
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            elapsed = time.time() - start_time
            
            response_text = response.text.strip()
            logger.info(f"[Gemini] Response time: {elapsed:.2f}s, length: {len(response_text)}")
            
            return self._clean_response(response_text)
            
        except Exception as e:
            logger.error(f"[Gemini] Error: {e}", exc_info=True)
            return self._handle_error(e)
    
    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        cached_content: Optional[str] = None,
    ) -> LLMResponse:
        """Generate response from conversation history.

        Args:
            cached_content: Gemini cache resource name (TASK-028). When
                provided the static system prompt is already in the cache;
                ``system_prompt`` should contain only the dynamic lead context.
        """
        if not self.is_configured:
            return LLMResponse(content=self.FALLBACK_RESPONSE)

        effective_temp = temperature if temperature is not None else self.temperature

        try:
            contents = self._convert_messages_to_native(messages)

            if cached_content:
                # Static system instruction lives in the cache.
                # Dynamic lead context comes in via system_prompt.
                if system_prompt:
                    contents = [
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"CONTEXTO ACTUAL:\n{system_prompt}")],
                        )
                    ] + contents
                config = types.GenerateContentConfig(
                    cached_content=cached_content,
                    max_output_tokens=self.max_tokens,
                    temperature=effective_temp,
                )
            else:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt if system_prompt else None,
                    max_output_tokens=self.max_tokens,
                    temperature=effective_temp,
                )

            start_time = time.time()
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            elapsed = time.time() - start_time

            text = response.text.strip() if response.text else ""
            logger.info(f"[Gemini] Messages response time: {elapsed:.2f}s, temp={effective_temp}")

            return LLMResponse(content=self._clean_response(text))

        except Exception as e:
            logger.error(f"[Gemini] Error in generate_with_messages: {e}", exc_info=True)
            return LLMResponse(content=self._handle_error(e))
    
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        system_prompt: Optional[str] = None,
        tool_executor: Optional[Callable] = None,
        cached_content: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generate response with function calling (or plain text when tools is empty).

        Args:
            cached_content: Gemini cache resource name (TASK-028). When
                provided the static system prompt is in the cache and
                ``system_prompt`` contains only the dynamic lead context.
        """
        if not self.is_configured:
            return self.FALLBACK_RESPONSE, []

        try:
            contents = self._convert_messages_to_native(messages)

            if cached_content:
                # Static system instruction is in the Gemini cache.
                # Dynamic lead context (if any) prepended to contents.
                if system_prompt:
                    contents = [
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"CONTEXTO ACTUAL:\n{system_prompt}")],
                        )
                    ] + contents
                base_config_kwargs: dict = {"cached_content": cached_content}
            else:
                base_config_kwargs = {
                    "system_instruction": system_prompt if system_prompt else None
                }

            if not tools:
                # No tools: plain text generation
                config = types.GenerateContentConfig(
                    **base_config_kwargs,
                    max_output_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                text = response.text.strip() if response.text else ""
                usage = None
                if getattr(response, "usage_metadata", None):
                    um = response.usage_metadata
                    inp = getattr(um, "prompt_token_count", 0) or 0
                    out = getattr(um, "candidates_token_count", 0) or 0
                    if inp or out:
                        usage = {"input_tokens": inp, "output_tokens": out}
                return self._clean_response(text), [], usage

            native_tools = self._convert_tools_to_native(tools)
            config = types.GenerateContentConfig(
                **base_config_kwargs,
                tools=native_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            
            function_calls_executed = []
            max_iterations = 5
            total_input_tokens = 0
            total_output_tokens = 0

            for iteration in range(max_iterations):
                logger.info(f"[Gemini] Tool calling iteration {iteration + 1}/{max_iterations}")
                
                start_time = time.time()
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config
                )
                elapsed = time.time() - start_time
                logger.info(f"[Gemini] API call time: {elapsed:.2f}s")
                # Accumulate usage for cost logging
                if getattr(response, "usage_metadata", None):
                    um = response.usage_metadata
                    total_input_tokens += getattr(um, "prompt_token_count", 0) or 0
                    total_output_tokens += getattr(um, "candidates_token_count", 0) or 0
                
                # Check for function calls
                function_calls = self._extract_function_calls(response)
                
                if not function_calls:
                    # No function calls, return text response
                    text = response.text.strip() if response.text else ""
                    usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                    return self._clean_response(text), function_calls_executed, usage
                
                # Execute function calls
                if tool_executor:
                    function_results = []
                    for fc in function_calls:
                        try:
                            result = await tool_executor(fc["name"], fc["args"])
                            function_results.append({
                                "name": fc["name"],
                                "response": {"result": str(result)}
                            })
                            function_calls_executed.append({
                                "name": fc["name"],
                                "args": fc["args"],
                                "result": result
                            })
                        except Exception as e:
                            logger.error(f"[Gemini] Tool execution error: {e}")
                            function_results.append({
                                "name": fc["name"],
                                "response": {"error": str(e)}
                            })
                    
                    # Add function call and results to conversation
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part(function_call=types.FunctionCall(
                            name=fc["name"],
                            args=fc["args"]
                        )) for fc in function_calls]
                    ))
                    
                    for fr in function_results:
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part(function_response=types.FunctionResponse(
                                name=fr["name"],
                                response=fr["response"]
                            ))]
                        ))
                else:
                    # No executor, return what we have
                    text = response.text.strip() if response.text else ""
                    usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                    return self._clean_response(text), [
                        {"name": fc["name"], "args": fc["args"]} for fc in function_calls
                    ], usage
            
            # Max iterations reached
            logger.warning("[Gemini] Max iterations reached in tool calling")
            usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
            return self.FALLBACK_RESPONSE, function_calls_executed, usage
            
        except Exception as e:
            logger.error(f"[Gemini] Error in generate_with_tools: {e}", exc_info=True)
            return self._handle_error(e), [], None
    
    async def generate_json(
        self,
        prompt: str,
        json_schema: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        if not self.is_configured:
            return {}
        
        try:
            json_prompt = f"{prompt}\n\nResponde SOLO con JSON válido, sin texto adicional."
            
            response = self._client.models.generate_content(
                model=self.model,
                contents=json_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=0.3,
                    response_mime_type="application/json"
                )
            )
            
            text = response.text.strip()
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            logger.warning(f"[Gemini] JSON parse error with response_mime_type: {e}, retrying without it")
        except Exception as e:
            logger.warning(f"[Gemini] generate_json with response_mime_type failed: {e}, retrying without it")

        # Fallback: retry without response_mime_type and do manual cleanup
        try:
            json_prompt = f"{prompt}\n\nResponde SOLO con JSON válido, sin texto adicional ni comentarios."
            
            response = self._client.models.generate_content(
                model=self.model,
                contents=json_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=0.1
                )
            )
            
            text = response.text.strip()
            text = self._clean_json_text(text)
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            logger.error(f"[Gemini] JSON parse error after cleanup: {e}")
            return {}
        except Exception as e:
            logger.error(f"[Gemini] Error in generate_json fallback: {e}", exc_info=True)
            return {}

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Best-effort cleanup of Gemini JSON output quirks."""
        import re
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])
        # Remove JS-style single-line comments
        text = re.sub(r'//[^\n]*', '', text)
        # Remove trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
        return text.strip()
    
    def _convert_messages_to_native(self, messages: List[LLMMessage]) -> List[types.Content]:
        """Convert unified messages to Gemini Content format"""
        contents = []
        for msg in messages:
            role = "user" if msg.role == MessageRole.USER else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg.content)]
            ))
        return contents
    
    def _normalize_schema_for_parameters(self, params: Any) -> Dict[str, Any]:
        """Build a schema dict that Gemini Schema model accepts (no None for any_of/items)."""
        if not params or not isinstance(params, dict):
            base = {"type": "object", "properties": {}, "required": []}
        else:
            base = {
                "type": params.get("type", "object"),
                "properties": params.get("properties") if isinstance(params.get("properties"), dict) else {},
                "required": params.get("required") if isinstance(params.get("required"), list) else [],
            }
        # SDK Schema model validates any_of/items; avoid None by not including them (minimal schema)
        return {k: v for k, v in base.items() if v is not None}

    def _convert_tools_to_native(self, tools: List[LLMToolDefinition]) -> List[types.Tool]:
        """Convert unified tools to Gemini Tool format. Use parameters= with schema dict (this SDK has no parameters_json_schema)."""
        function_declarations = []
        for tool in tools:
            schema_dict = self._normalize_schema_for_parameters(tool.parameters)
            try:
                decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=schema_dict
                )
            except Exception as e:
                logger.warning("[Gemini] FunctionDeclaration with parameters failed (%s), trying without parameters", e)
                decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or "",
                )
            function_declarations.append(decl)
        return [types.Tool(function_declarations=function_declarations)]
    
    def _extract_function_calls(self, response) -> List[Dict[str, Any]]:
        """Extract function calls from Gemini response"""
        calls = []
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            calls.append({
                                "name": fc.name,
                                "args": dict(fc.args) if fc.args else {}
                            })
        return calls
    
    def _handle_error(self, error: Exception) -> str:
        """Handle API errors with appropriate fallback messages"""
        error_msg = str(error)
        
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return "Lo siento, estoy experimentando problemas temporales. Intenta de nuevo en unos momentos."
        
        if "503" in error_msg or "UNAVAILABLE" in error_msg:
            return "El servicio está temporalmente sobrecargado. Intenta de nuevo en unos momentos."
        
        return self.FALLBACK_RESPONSE
    
    def _clean_response(self, text: str) -> str:
        """Clean Gemini-specific response artifacts. Only use fallback when there is no real content."""
        if not text or not text.strip():
            return self.FALLBACK_RESPONSE
        
        cleaned = text.strip()
        
        # Remove common Gemini artifacts
        for marker in ["RESPUESTA:", "R:", "RESPONSE:"]:
            if marker in cleaned:
                parts = cleaned.split(marker)
                cleaned = parts[-1].strip()
        
        # Remove context markers
        lines = []
        for line in cleaned.split('\n'):
            if not line.startswith(('P:', 'INFO_OK:', 'H:', 'M:')):
                lines.append(line)
        cleaned = '\n'.join(lines).strip()
        
        # Return any non-empty content; only fallback when truly empty after cleaning
        return cleaned if cleaned else self.FALLBACK_RESPONSE

    async def stream_generate(
        self,
        messages: List["LLMMessage"],
        system_prompt: Optional[str] = None,
    ):
        """
        Async generator that yields text chunks from Gemini's streaming API.
        Falls back to yielding the complete response as one chunk on error.
        """
        import asyncio

        if not self.is_configured:
            yield self.FALLBACK_RESPONSE
            return

        contents = self._convert_messages_to_native(messages)
        if system_prompt:
            system_content = types.Content(
                role="user",
                parts=[types.Part(text=f"INSTRUCCIONES: {system_prompt}\n\n---\n\nCONTINÚA:")],
            )
            contents = [system_content] + contents

        config = types.GenerateContentConfig(
            max_output_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        try:
            # SDK is synchronous — run in thread to avoid blocking event loop
            queue: asyncio.Queue = asyncio.Queue()

            def _stream_to_queue():
                try:
                    for chunk in self._client.models.generate_content_stream(
                        model=self.model,
                        contents=contents,
                        config=config,
                    ):
                        text = getattr(chunk, "text", None) or ""
                        if text:
                            queue.put_nowait(text)
                finally:
                    queue.put_nowait(None)  # sentinel

            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _stream_to_queue)

            while True:
                chunk_text = await queue.get()
                if chunk_text is None:
                    break
                yield chunk_text

        except Exception as exc:
            logger.warning("[Gemini] Streaming failed (%s), yielding full response", exc)
            try:
                full = await asyncio.to_thread(
                    lambda: self._client.models.generate_content(
                        model=self.model, contents=contents, config=config
                    ).text
                )
                yield full or self.FALLBACK_RESPONSE
            except Exception:
                yield self.FALLBACK_RESPONSE
