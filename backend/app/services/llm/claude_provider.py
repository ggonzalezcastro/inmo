"""
Anthropic Claude LLM Provider

Implements the BaseLLMProvider interface for Anthropic Claude API.
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


class ClaudeProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM Provider implementation.
    
    Wraps the Anthropic SDK to provide a unified interface.
    Requires: pip install anthropic
    """
    
    def __init__(
        self, 
        api_key: str = None, 
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ):
        api_key = api_key or settings.ANTHROPIC_API_KEY
        model = model or getattr(settings, 'CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        super().__init__(api_key, model, **kwargs)
        
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize client (lazy import to avoid hard dependency)
        if self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
                logger.info(f"ClaudeProvider initialized with model: {self.model}")
            except ImportError:
                logger.error("ClaudeProvider requires 'anthropic' package. Install with: pip install anthropic")
                self._client = None
        else:
            logger.warning("ClaudeProvider: No API key provided")
    
    @property
    def is_configured(self) -> bool:
        return bool(self._client and self.api_key)
    
    async def generate_response(self, prompt: str) -> str:
        """Generate simple text response from Claude"""
        if not self.is_configured:
            logger.warning("[Claude] Not configured, using fallback")
            return self.FALLBACK_RESPONSE
        
        try:
            start_time = time.time()
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            elapsed = time.time() - start_time
            
            response_text = message.content[0].text
            logger.info(f"[Claude] Response time: {elapsed:.2f}s, length: {len(response_text)}")
            
            return self._clean_response(response_text)
            
        except Exception as e:
            logger.error(f"[Claude] Error: {e}", exc_info=True)
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

            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": effective_temp,
                "messages": native_messages,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            start_time = time.time()
            message = await self._client.messages.create(**kwargs)
            elapsed = time.time() - start_time

            text = message.content[0].text if message.content else ""
            logger.info(f"[Claude] Messages response time: {elapsed:.2f}s, temp={effective_temp}")
            
            return LLMResponse(
                content=self._clean_response(text),
                finish_reason=message.stop_reason or "stop",
                usage={
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens
                } if message.usage else None
            )
            
        except Exception as e:
            logger.error(f"[Claude] Error in generate_with_messages: {e}", exc_info=True)
            return LLMResponse(content=self._handle_error(e))
    
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        system_prompt: Optional[str] = None,
        tool_executor: Optional[Callable] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generate response with tool use"""
        if not self.is_configured:
            return self.FALLBACK_RESPONSE, []
        
        try:
            native_messages = self._convert_messages_to_native(messages)
            native_tools = self._convert_tools_to_native(tools)
            
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": native_messages,
                "tools": native_tools
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            function_calls_executed = []
            max_iterations = 5
            total_input_tokens = 0
            total_output_tokens = 0

            for iteration in range(max_iterations):
                logger.info(f"[Claude] Tool calling iteration {iteration + 1}/{max_iterations}")
                
                start_time = time.time()
                response = await self._client.messages.create(**kwargs)
                elapsed = time.time() - start_time
                logger.info(f"[Claude] API call time: {elapsed:.2f}s")
                if getattr(response, "usage", None):
                    total_input_tokens += response.usage.input_tokens or 0
                    total_output_tokens += response.usage.output_tokens or 0
                
                # Check if response has tool use
                tool_uses = [block for block in response.content if block.type == "tool_use"]
                
                if not tool_uses:
                    # No tool calls, extract text response
                    text_blocks = [block.text for block in response.content if block.type == "text"]
                    usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                    return self._clean_response("".join(text_blocks)), function_calls_executed, usage
                
                # Execute tool calls
                if tool_executor:
                    tool_results = []
                    for tool_use in tool_uses:
                        try:
                            result = await tool_executor(tool_use.name, tool_use.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(result)
                            })
                            function_calls_executed.append({
                                "name": tool_use.name,
                                "args": tool_use.input,
                                "result": result
                            })
                        except Exception as e:
                            logger.error(f"[Claude] Tool execution error: {e}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": f"Error: {str(e)}",
                                "is_error": True
                            })
                    
                    # Add assistant response and tool results
                    kwargs["messages"].append({
                        "role": "assistant",
                        "content": response.content
                    })
                    kwargs["messages"].append({
                        "role": "user",
                        "content": tool_results
                    })
                else:
                    # No executor, return tool calls info
                    text_blocks = [block.text for block in response.content if block.type == "text"]
                    usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                    return self._clean_response("".join(text_blocks)), [
                        {"name": tu.name, "args": tu.input} for tu in tool_uses
                    ], usage
            
            logger.warning("[Claude] Max iterations reached")
            usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
            return self.FALLBACK_RESPONSE, function_calls_executed, usage
            
        except Exception as e:
            logger.error(f"[Claude] Error in generate_with_tools: {e}", exc_info=True)
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
            json_prompt = f"{prompt}\n\nResponde SOLO con JSON válido, sin texto adicional ni bloques de código."
            
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": json_prompt}]
            )
            
            text = message.content[0].text.strip()
            
            # Clean JSON from markdown
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            logger.error(f"[Claude] JSON parse error: {e}")
            return {}
        except Exception as e:
            logger.error(f"[Claude] Error in generate_json: {e}", exc_info=True)
            return {}
    
    def _convert_messages_to_native(self, messages: List[LLMMessage]) -> List[Dict]:
        """Convert unified messages to Claude format"""
        native_messages = []
        for msg in messages:
            role = "user" if msg.role in [MessageRole.USER, MessageRole.SYSTEM] else "assistant"
            native_messages.append({
                "role": role,
                "content": msg.content
            })
        return native_messages
    
    def _convert_tools_to_native(self, tools: List[LLMToolDefinition]) -> List[Dict]:
        """Convert unified tools to Claude tool format"""
        return [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters
        } for tool in tools]
    
    def _handle_error(self, error: Exception) -> str:
        """Handle API errors"""
        error_msg = str(error)
        
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            return "El servicio está temporalmente sobrecargado. Intenta de nuevo en unos momentos."
        
        if "authentication" in error_msg.lower() or "401" in error_msg:
            logger.error("[Claude] Authentication error - check API key")
            return self.FALLBACK_RESPONSE
        
        return self.FALLBACK_RESPONSE
