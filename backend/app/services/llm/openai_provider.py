"""
OpenAI GPT LLM Provider

Implements the BaseLLMProvider interface for OpenAI API.
"""
import json
import time
import logging
from typing import Dict, Any, List, Tuple, Callable, Optional

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


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI GPT LLM Provider implementation.
    
    Wraps the OpenAI SDK to provide a unified interface.
    Requires: pip install openai
    """
    
    def __init__(
        self, 
        api_key: str = None, 
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ):
        api_key = api_key or settings.OPENAI_API_KEY
        model = model or getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
        super().__init__(api_key, model, **kwargs)
        
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize client (lazy import)
        if self.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(f"OpenAIProvider initialized with model: {self.model}")
            except ImportError:
                logger.error("OpenAIProvider requires 'openai' package. Install with: pip install openai")
                self._client = None
        else:
            logger.warning("OpenAIProvider: No API key provided")
    
    @property
    def is_configured(self) -> bool:
        return bool(self._client and self.api_key)
    
    async def generate_response(self, prompt: str) -> str:
        """Generate simple text response from OpenAI"""
        if not self.is_configured:
            logger.warning("[OpenAI] Not configured, using fallback")
            return self.FALLBACK_RESPONSE
        
        try:
            start_time = time.time()
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            elapsed = time.time() - start_time
            
            response_text = response.choices[0].message.content
            logger.info(f"[OpenAI] Response time: {elapsed:.2f}s, length: {len(response_text)}")
            
            return self._clean_response(response_text)
            
        except Exception as e:
            logger.error(f"[OpenAI] Error: {e}", exc_info=True)
            return self._handle_error(e)
    
    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Generate response from conversation history"""
        if not self.is_configured:
            return LLMResponse(content=self.FALLBACK_RESPONSE)
        
        effective_temp = temperature if temperature is not None else self.temperature

        try:
            native_messages = self._convert_messages_to_native(messages)

            # Add system prompt at the beginning
            if system_prompt:
                native_messages.insert(0, {"role": "system", "content": system_prompt})

            start_time = time.time()
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=effective_temp,
                messages=native_messages,
            )
            elapsed = time.time() - start_time

            choice = response.choices[0]
            text = choice.message.content or ""
            logger.info(f"[OpenAI] Messages response time: {elapsed:.2f}s, temp={effective_temp}")
            
            return LLMResponse(
                content=self._clean_response(text),
                finish_reason=choice.finish_reason or "stop",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else None
            )
            
        except Exception as e:
            logger.error(f"[OpenAI] Error in generate_with_messages: {e}", exc_info=True)
            return LLMResponse(content=self._handle_error(e))
    
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        system_prompt: Optional[str] = None,
        tool_executor: Optional[Callable] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generate response with function calling"""
        if not self.is_configured:
            return self.FALLBACK_RESPONSE, []
        
        try:
            native_messages = self._convert_messages_to_native(messages)
            native_tools = self._convert_tools_to_native(tools)
            
            if system_prompt:
                native_messages.insert(0, {"role": "system", "content": system_prompt})
            
            function_calls_executed = []
            max_iterations = 5
            
            for iteration in range(max_iterations):
                logger.info(f"[OpenAI] Tool calling iteration {iteration + 1}/{max_iterations}")
                
                start_time = time.time()
                response = await self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=native_messages,
                    tools=native_tools,
                    tool_choice="auto"
                )
                elapsed = time.time() - start_time
                logger.info(f"[OpenAI] API call time: {elapsed:.2f}s")
                
                choice = response.choices[0]
                message = choice.message
                
                # Check for tool calls
                if not message.tool_calls:
                    # No tool calls, return text
                    return self._clean_response(message.content or ""), function_calls_executed
                
                # Add assistant message with tool calls
                native_messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                # Execute tool calls
                if tool_executor:
                    for tool_call in message.tool_calls:
                        func_name = tool_call.function.name
                        func_args = json.loads(tool_call.function.arguments)
                        
                        try:
                            result = await tool_executor(func_name, func_args)
                            native_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(result)
                            })
                            function_calls_executed.append({
                                "name": func_name,
                                "args": func_args,
                                "result": result
                            })
                        except Exception as e:
                            logger.error(f"[OpenAI] Tool execution error: {e}")
                            native_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": f"Error: {str(e)}"
                            })
                else:
                    # No executor, return info
                    return message.content or self.FALLBACK_RESPONSE, [
                        {"name": tc.function.name, "args": json.loads(tc.function.arguments)}
                        for tc in message.tool_calls
                    ]
            
            logger.warning("[OpenAI] Max iterations reached")
            return self.FALLBACK_RESPONSE, function_calls_executed
            
        except Exception as e:
            logger.error(f"[OpenAI] Error in generate_with_tools: {e}", exc_info=True)
            return self._handle_error(e), []
    
    async def generate_json(
        self,
        prompt: str,
        json_schema: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        if not self.is_configured:
            return {}
        
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages
            }
            
            # Use JSON mode if available
            if self.model.startswith("gpt-4"):
                kwargs["response_format"] = {"type": "json_object"}
            
            response = await self._client.chat.completions.create(**kwargs)
            
            text = response.choices[0].message.content.strip()
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            logger.error(f"[OpenAI] JSON parse error: {e}")
            return {}
        except Exception as e:
            logger.error(f"[OpenAI] Error in generate_json: {e}", exc_info=True)
            return {}
    
    def _convert_messages_to_native(self, messages: List[LLMMessage]) -> List[Dict]:
        """Convert unified messages to OpenAI format"""
        native_messages = []
        for msg in messages:
            role = msg.role.value  # system, user, assistant, tool
            native_messages.append({
                "role": role,
                "content": msg.content
            })
        return native_messages
    
    def _convert_tools_to_native(self, tools: List[LLMToolDefinition]) -> List[Dict]:
        """Convert unified tools to OpenAI function format"""
        return [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        } for tool in tools]
    
    def _handle_error(self, error: Exception) -> str:
        """Handle API errors"""
        error_msg = str(error)
        
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            return "El servicio está temporalmente sobrecargado. Intenta de nuevo."
        
        if "insufficient_quota" in error_msg.lower():
            return "Se ha agotado la cuota de la API. Contacta al administrador."
        
        return self.FALLBACK_RESPONSE
