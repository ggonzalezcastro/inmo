"""
Base LLM Provider - Abstract Base Class

Defines the contract that all LLM providers must implement.
This enables swapping between Gemini, Claude, OpenAI without changing business logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Callable, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Standard message roles across all providers"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class LLMMessage:
    """
    Unified message format for all LLM providers.
    Each provider translates this to their native format.
    """
    role: MessageRole
    content: str
    name: Optional[str] = None  # For tool messages
    tool_call_id: Optional[str] = None  # For tool results


@dataclass
class LLMToolCall:
    """Represents a function/tool call from the LLM"""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass 
class LLMToolDefinition:
    """
    Unified tool/function definition format.
    
    Each provider translates this to their native format:
    - Gemini: types.Tool with FunctionDeclaration
    - Claude: tool definition in messages
    - OpenAI: functions array
    """
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format


@dataclass
class LLMResponse:
    """Unified response format from LLM providers"""
    content: str
    tool_calls: List[LLMToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Optional[Dict[str, int]] = None


class BaseLLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.
    
    All concrete providers (Gemini, Claude, OpenAI) must implement these methods.
    This allows the application to switch between providers without changing
    the business logic in LLMService.
    
    Example usage:
        provider = get_llm_provider()  # Gets configured provider
        response = await provider.generate_response("Hello!")
    """
    
    FALLBACK_RESPONSE = "Gracias por tu mensaje. Un agente estará contigo pronto para ayudarte."
    
    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initialize the provider.
        
        Args:
            api_key: API key for the provider
            model: Model identifier to use
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.model = model
        self.config = kwargs
        self._client = None
    
    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured"""
        pass
    
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """
        Generate a simple text response.
        
        Args:
            prompt: The input prompt/question
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Generate response from a conversation history.
        
        Args:
            messages: List of conversation messages
            system_prompt: Optional system instruction
            
        Returns:
            LLMResponse with content and potential tool calls
        """
        pass
    
    @abstractmethod
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        system_prompt: Optional[str] = None,
        tool_executor: Optional[Callable] = None
    ) -> Tuple[str, List[Dict[str, Any]], Optional[Dict[str, int]]]:
        """
        Generate response with function/tool calling support.
        
        Args:
            messages: Conversation history
            tools: Available tool definitions
            system_prompt: System instruction
            tool_executor: Async function to execute tools: (name, args) -> result
            
        Returns:
            Tuple of (final_response_text, list_of_executed_tool_calls, optional_usage).
            usage may be {"input_tokens": int, "output_tokens": int} for cost logging.
        """
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        json_schema: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response.
        
        Args:
            prompt: The input prompt requesting JSON
            json_schema: Optional JSON schema for validation
            
        Returns:
            Parsed JSON dictionary
        """
        pass
    
    def _clean_response(self, text: str) -> str:
        """
        Clean LLM response text.
        Can be overridden by providers for specific cleaning.
        """
        if not text:
            return self.FALLBACK_RESPONSE
        
        cleaned = text.strip()
        
        # Remove common artifacts
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if len(lines) > 2:
                cleaned = "\n".join(lines[1:-1])
        
        return cleaned if cleaned else self.FALLBACK_RESPONSE
    
    def _convert_messages_to_native(self, messages: List[LLMMessage]) -> Any:
        """
        Convert unified messages to provider-specific format.
        Must be implemented by concrete providers.
        """
        raise NotImplementedError("Subclass must implement _convert_messages_to_native")
    
    def _convert_tools_to_native(self, tools: List[LLMToolDefinition]) -> Any:
        """
        Convert unified tool definitions to provider-specific format.
        Must be implemented by concrete providers.
        """
        raise NotImplementedError("Subclass must implement _convert_tools_to_native")
