"""
OpenAI GPT LLM Provider

Implements the BaseLLMProvider interface for OpenAI API.
"""
import json
import os
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


def _openrouter_cost(response) -> Optional[float]:
    """Extract actual cost USD from OpenRouter response (model_extra["cost"])."""
    try:
        extra = getattr(response.usage, "model_extra", None) or {}
        cost = extra.get("cost")
        if cost is not None:
            return float(cost)
    except Exception:
        pass
    return None


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
        base_url: str = None,
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
                effective_base_url = base_url or getattr(settings, 'OPENAI_BASE_URL', '') or None
                extra_headers = {}
                if effective_base_url and "openrouter.ai" in effective_base_url:
                    extra_headers = {
                        "HTTP-Referer": "https://captame.cl",
                        "X-Title": "Captame Inmo",
                    }
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=effective_base_url,
                    default_headers=extra_headers or None,
                )
                # Track whether we are talking to OpenRouter (used to gate
                # OpenRouter-specific features like prompt-caching breakpoints).
                self._is_openrouter = bool(effective_base_url and "openrouter.ai" in effective_base_url)
                # OpenRouter provider-routing preferences. Setting
                # ``OPENROUTER_PROVIDER_SORT=latency`` routes each request to
                # the lowest-latency backend endpoint (vs throughput / cost).
                # Cuts ~50-150ms TTFT on warm calls per research.
                self._openrouter_extra_body: Optional[Dict[str, Any]] = None
                if self._is_openrouter:
                    _sort = os.getenv("OPENROUTER_PROVIDER_SORT", "").strip().lower()
                    if _sort in ("latency", "throughput", "price"):
                        self._openrouter_extra_body = {"provider": {"sort": _sort}}
                        logger.info(f"OpenAIProvider OpenRouter provider.sort={_sort}")
                logger.info(f"OpenAIProvider initialized with model: {self.model}" + (f" @ {effective_base_url}" if effective_base_url else ""))
            except ImportError:
                logger.error("OpenAIProvider requires 'openai' package. Install with: pip install openai")
                self._client = None
        else:
            logger.warning("OpenAIProvider: No API key provided")
    
    @property
    def is_configured(self) -> bool:
        return bool(self._client and self.api_key)

    def _build_system_message(self, system_prompt: str) -> Dict[str, Any]:
        """
        Build a `system` chat message, enabling OpenRouter prompt caching
        when routed to a model that supports it (currently Gemini & Claude).

        OpenRouter requires an explicit `cache_control: {type: "ephemeral"}`
        breakpoint on the last content block to cache the stable prefix
        (see https://openrouter.ai/docs/features/prompt-caching).

        Gemini 2.5 Flash minimum cacheable prompt is 1024 tokens; below
        that the breakpoint is silently ignored, so it's always safe to set.
        Cache reads cost 0.25x of input — and crucially shave provider-side
        latency since the prefix is not re-encoded.
        """
        model_l = (self.model or "").lower()
        cache_eligible = self._is_openrouter and (
            "gemini" in model_l
            or "claude" in model_l
            or "anthropic" in model_l
        )
        if not cache_eligible or not system_prompt:
            return {"role": "system", "content": system_prompt}
        return {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }

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

            # Add system prompt at the beginning (with OpenRouter cache
            # breakpoint when routed to a supported model — see _build_system_message)
            if system_prompt:
                native_messages.insert(0, self._build_system_message(system_prompt))

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
            # Expose OpenRouter prompt-cache stats when present (Gemini/Claude).
            _cached_tokens = 0
            try:
                _details = getattr(response.usage, "prompt_tokens_details", None)
                if _details is not None:
                    _cached_tokens = getattr(_details, "cached_tokens", 0) or 0
            except Exception:
                _cached_tokens = 0
            logger.info(
                f"[OpenAI] Messages response time: {elapsed:.2f}s, temp={effective_temp}"
                + (f", cached_tokens={_cached_tokens}" if _cached_tokens else "")
            )
            
            _usage = None
            if response.usage:
                _usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                _cost = _openrouter_cost(response)
                if _cost is not None:
                    _usage["actual_cost_usd"] = _cost
            return LLMResponse(
                content=self._clean_response(text),
                finish_reason=choice.finish_reason or "stop",
                usage=_usage,
            )
            
        except Exception as e:
            logger.error(f"[OpenAI] Error in generate_with_messages: {e}", exc_info=True)
            return LLMResponse(content=self._handle_error(e))
    
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        system_prompt: Optional[str] = None,
        tool_executor: Optional[Callable] = None,
        cached_content: Optional[str] = None,     # ignored — Gemini-only feature
        tool_mode_override: Optional[str] = None, # ignored — Gemini-only feature
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generate response with function calling.

        When a streaming text callback is installed via
        :func:`app.services.llm.streaming_context.set_text_stream_callback`
        (typically by the voice pipeline), text deltas from each iteration
        are forwarded to the callback as they arrive. This lets Fish TTS
        start synthesising the first sentence ~150 ms after the LLM
        response starts streaming, instead of waiting ~1500 ms for the
        full response. Tool-call deltas are accumulated and processed at
        end-of-stream as before.
        """
        if not self.is_configured:
            return self.FALLBACK_RESPONSE, [], None, None

        # Optional streaming hook installed by the voice processor.
        from app.services.llm.streaming_context import get_text_stream_callback
        text_stream_cb = get_text_stream_callback()
        logger.info(
            "[STREAM] generate_with_tools streaming=%s tools=%d",
            "ACTIVE" if text_stream_cb is not None else "OFF",
            len(tools or []),
        )

        try:
            native_messages = self._convert_messages_to_native(messages)
            native_tools = self._convert_tools_to_native(tools)
            
            if system_prompt:
                native_messages.insert(0, self._build_system_message(system_prompt))
            
            function_calls_executed = []
            max_iterations = 5
            total_input_tokens = 0
            total_output_tokens = 0
            total_actual_cost: Optional[float] = None

            for iteration in range(max_iterations):
                logger.info(f"[OpenAI] Tool calling iteration {iteration + 1}/{max_iterations}")

                start_time = time.time()
                if text_stream_cb is not None:
                    # Streaming path — forward text deltas to the callback while
                    # accumulating tool_calls and final state for the loop.
                    text_buf, tool_calls, finish_reason, usage_info = await self._stream_completion(
                        native_messages=native_messages,
                        native_tools=native_tools,
                        text_callback=text_stream_cb,
                    )
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[OpenAI] API call (stream) time: {elapsed:.2f}s "
                        f"tool_calls={len(tool_calls)} text_chars={len(text_buf)}"
                    )
                    if usage_info:
                        total_input_tokens += usage_info.get("prompt_tokens", 0) or 0
                        total_output_tokens += usage_info.get("completion_tokens", 0) or 0
                        if usage_info.get("actual_cost_usd") is not None:
                            total_actual_cost = (total_actual_cost or 0.0) + usage_info["actual_cost_usd"]

                    if not tool_calls:
                        # No tool calls — return accumulated text. The callback
                        # has already pushed it sentence-by-sentence to TTS.
                        usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                        if usage and total_actual_cost is not None:
                            usage["actual_cost_usd"] = round(total_actual_cost, 8)
                        return self._clean_response(text_buf), function_calls_executed, usage, None

                    # Tool calls present — record assistant turn and execute.
                    native_messages.append({
                        "role": "assistant",
                        "content": text_buf or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]},
                            }
                            for tc in tool_calls
                        ],
                    })

                    if tool_executor:
                        for tc in tool_calls:
                            try:
                                func_args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                            except Exception:
                                func_args = {}
                            try:
                                result = await tool_executor(tc["name"], func_args)
                                native_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": str(result),
                                })
                                function_calls_executed.append({
                                    "name": tc["name"], "args": func_args, "result": result,
                                })
                            except Exception as e:
                                logger.error(f"[OpenAI] Tool execution error: {e}")
                                native_messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": f"Error: {str(e)}",
                                })
                    else:
                        usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                        if usage and total_actual_cost is not None:
                            usage["actual_cost_usd"] = round(total_actual_cost, 8)
                        return text_buf or self.FALLBACK_RESPONSE, [
                            {"name": tc["name"], "args": json.loads(tc["arguments"]) if tc["arguments"] else {}}
                            for tc in tool_calls
                        ], usage, None
                    continue  # next iteration — handled tools, get final response

                response = await self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=native_messages,
                    tools=native_tools,
                    tool_choice="auto",
                    extra_body=self._openrouter_extra_body or None,
                )
                elapsed = time.time() - start_time
                _or_provider = getattr(response, "provider", None) or (
                    getattr(response, "model_extra", {}) or {}
                ).get("provider")
                logger.info(
                    "[OpenAI] API call time: %.2fs%s",
                    elapsed,
                    f" or_provider={_or_provider}" if _or_provider else "",
                )
                if getattr(response, "usage", None):
                    total_input_tokens += response.usage.prompt_tokens or 0
                    total_output_tokens += response.usage.completion_tokens or 0
                    _iter_cost = _openrouter_cost(response)
                    if _iter_cost is not None:
                        total_actual_cost = (total_actual_cost or 0.0) + _iter_cost
                
                choice = response.choices[0]
                message = choice.message
                
                # Check for tool calls
                if not message.tool_calls:
                    # No tool calls, return text
                    usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                    if usage and total_actual_cost is not None:
                        usage["actual_cost_usd"] = round(total_actual_cost, 8)
                    return self._clean_response(message.content or ""), function_calls_executed, usage, None
                
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
                    usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
                    if usage and total_actual_cost is not None:
                        usage["actual_cost_usd"] = round(total_actual_cost, 8)
                    return message.content or self.FALLBACK_RESPONSE, [
                        {"name": tc.function.name, "args": json.loads(tc.function.arguments)}
                        for tc in message.tool_calls
                    ], usage, None

            logger.warning("[OpenAI] Max iterations reached")
            usage = {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens} if (total_input_tokens or total_output_tokens) else None
            if usage and total_actual_cost is not None:
                usage["actual_cost_usd"] = round(total_actual_cost, 8)
            return self.FALLBACK_RESPONSE, function_calls_executed, usage, None
            
        except Exception as e:
            logger.error(f"[OpenAI] Error in generate_with_tools: {e}", exc_info=True)
            return self._handle_error(e), [], None, None

    async def _stream_completion(
        self,
        native_messages: List[Dict[str, Any]],
        native_tools: List[Dict[str, Any]],
        text_callback: Callable,
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
        """Stream a chat completion and forward text deltas to ``text_callback``.

        Returns ``(text, tool_calls, finish_reason, usage)`` where ``tool_calls``
        is a list of ``{id, name, arguments}`` dicts assembled from streamed
        deltas. The text content is also returned so callers can persist or
        inspect it without re-buffering from the callback.
        """
        text_buf: List[str] = []
        # tool_calls indexed by stream-delta index — OpenAI streams them as
        # partial fragments addressed by index, so we accumulate by index.
        tool_acc: Dict[int, Dict[str, str]] = {}
        finish_reason: Optional[str] = None
        usage_info: Optional[Dict[str, Any]] = None

        stream = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=native_messages,
            tools=native_tools,
            tool_choice="auto",
            stream=True,
            stream_options={"include_usage": True},
            extra_body=self._openrouter_extra_body or None,
        )

        async for chunk in stream:
            # Usage chunk arrives at end (when include_usage=True).
            if getattr(chunk, "usage", None):
                try:
                    usage_info = {
                        "prompt_tokens": chunk.usage.prompt_tokens or 0,
                        "completion_tokens": chunk.usage.completion_tokens or 0,
                    }
                    _cost = _openrouter_cost(chunk)
                    if _cost is not None:
                        usage_info["actual_cost_usd"] = _cost
                except Exception:
                    pass

            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue

            # Text content delta.
            content_piece = getattr(delta, "content", None)
            if content_piece:
                text_buf.append(content_piece)
                try:
                    await text_callback(content_piece)
                except Exception as cb_err:
                    logger.warning(f"[OpenAI] text_callback raised: {cb_err}")

            # Tool-call deltas — OpenAI sends fragments addressed by index.
            tc_deltas = getattr(delta, "tool_calls", None)
            if tc_deltas:
                for tc in tc_deltas:
                    idx = getattr(tc, "index", 0) or 0
                    slot = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if getattr(tc, "id", None):
                        slot["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            slot["arguments"] += fn.arguments

            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

        tool_calls = [tool_acc[i] for i in sorted(tool_acc.keys()) if tool_acc[i].get("name")]
        return "".join(text_buf), tool_calls, finish_reason, usage_info

    async def generate_json(
        self,
        prompt: str,
        json_schema: Optional[Dict] = None
    ) -> tuple[Dict[str, Any], Optional[Dict]]:
        """Generate structured JSON response. Returns (result, usage)."""
        if not self.is_configured:
            return {}, None

        try:
            messages = [{"role": "user", "content": prompt}]
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }

            response = await self._client.chat.completions.create(**kwargs)

            usage = None
            if getattr(response, "usage", None):
                usage = {
                    "input_tokens": response.usage.prompt_tokens or 0,
                    "output_tokens": response.usage.completion_tokens or 0,
                }
                _cost = _openrouter_cost(response)
                if _cost is not None:
                    usage["actual_cost_usd"] = _cost

            text = response.choices[0].message.content.strip()
            return self._parse_json(text), usage

        except Exception as e:
            logger.error(f"[OpenAI] Error in generate_json: {e}", exc_info=True)
            return {}, None

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Parse JSON from model output, stripping markdown code blocks if present."""
        import re
        text = text.strip()
        # Strip ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("[OpenAI] JSON parse error on: %s", text[:200])
            return {}
    
    def _convert_messages_to_native(self, messages: List[LLMMessage]) -> List[Dict]:
        """Convert unified messages to OpenAI format"""
        native_messages = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
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
