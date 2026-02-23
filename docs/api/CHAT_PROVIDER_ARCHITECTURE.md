# 🔄 Arquitectura de Chat Providers - Análisis y Propuesta de Desacoplamiento

## 📋 Resumen Ejecutivo

Este documento analiza la implementación actual del sistema de chat y propone una arquitectura desacoplada que permitirá soportar múltiples proveedores de mensajería (WhatsApp/Meta, Instagram, Facebook, TikTok, etc.) de forma similar a como se implementó el sistema de VoiceProviders.

## 🔍 Estado Actual - Análisis de Acoplamiento

### Problemas Identificados

#### 1. **Acoplamiento en el Modelo de Datos**
```python
# backend/app/models/telegram_message.py
class TelegramMessage(Base, IdMixin):
    """Telegram message history"""
    __tablename__ = "telegram_messages"
    
    # ❌ Campos específicos de Telegram
    telegram_user_id = Column(Integer, nullable=False, index=True)
    telegram_username = Column(String(100), nullable=True)
    telegram_message_id = Column(String(100), nullable=True, unique=True)
```

**Problema**: El modelo está completamente acoplado a Telegram. Agregar WhatsApp requeriría crear `WhatsAppMessage`, duplicando lógica.

#### 2. **Acoplamiento en los Servicios**
```python
# backend/app/services/activity_service.py
async def log_telegram_message(
    db: AsyncSession,
    lead_id: int,
    telegram_user_id: int,  # ❌ Específico de Telegram
    message_text: str,
    direction: str,
    ai_used: bool = True
) -> TelegramMessage:  # ❌ Retorna tipo específico
```

**Problema**: Los servicios asumen que solo existe Telegram como proveedor de chat.

#### 3. **Acoplamiento en las Rutas**
```python
# backend/app/routes/chat.py
# ✅ La ruta usa ChatOrchestratorService (bueno)
# ❌ Pero al obtener mensajes usa directamente TelegramMessage
from app.models.telegram_message import TelegramMessage

messages_result = await db.execute(
    select(TelegramMessage)
    .where(TelegramMessage.lead_id == lead_id)
```

#### 4. **Sin Configuración por Broker**
- No existe `BrokerChatConfig` (equivalente a `BrokerVoiceConfig`)
- No hay forma de configurar diferentes proveedores de chat por broker
- Los tokens y credenciales están hardcodeados en settings globales

## 🎯 Arquitectura Propuesta - Chat Provider Pattern

### Inspiración: Sistema de Voice Providers

El sistema de voz ya implementa un patrón desacoplado:

```
VoiceProvider (Abstract)
    ├── VapiProvider
    ├── TwilioProvider (futuro)
    └── CustomProvider (futuro)
    
BrokerVoiceConfig
    ├── phone_number_id
    ├── assistant_id_default
    └── assistant_id_by_type
```

### Arquitectura Propuesta para Chat

```
ChatProvider (Abstract)
    ├── TelegramProvider
    ├── WhatsAppProvider (Meta)
    ├── InstagramProvider
    ├── FacebookProvider
    ├── TikTokProvider
    └── WebChatProvider

BrokerChatConfig
    ├── provider_type (telegram, whatsapp, instagram, etc.)
    ├── provider_credentials (JSONB)
    ├── webhook_config (JSONB)
    └── enabled_channels (Array)
```

## 📐 Diseño Detallado

### 1. Modelo Genérico de Mensajes

```python
# backend/app/models/chat_message.py
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

class MessageDirection(str, Enum):
    INBOUND = "in"
    OUTBOUND = "out"

class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class ChatProvider(str, Enum):
    """Supported chat providers"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    WEBCHAT = "webchat"

class ChatMessage(Base, IdMixin, TimestampMixin):
    """Generic chat message - provider agnostic"""
    
    __tablename__ = "chat_messages"
    
    # Relaciones básicas
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Proveedor
    provider = Column(SQLEnum(ChatProvider), nullable=False, index=True)
    
    # Identificadores genéricos del canal
    channel_user_id = Column(String(255), nullable=False, index=True)  # telegram_id, whatsapp_number, instagram_handle
    channel_username = Column(String(255), nullable=True)
    channel_message_id = Column(String(255), nullable=True, index=True)
    
    # Datos del mensaje
    message_text = Column(Text, nullable=False)
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SENT, nullable=False)
    
    # Metadata específica del proveedor (JSONB para flexibilidad)
    provider_metadata = Column(JSONB, nullable=True)
    # Ejemplos:
    # Telegram: {"chat_id": 123, "message_type": "text", "reply_to_message_id": 456}
    # WhatsApp: {"wamid": "abc123", "context": {...}, "type": "text"}
    # Instagram: {"ig_id": "xyz", "story_reply": true}
    
    # Attachments (media, files, etc.)
    attachments = Column(JSONB, nullable=True)
    # Ejemplo: [{"type": "image", "url": "...", "mime_type": "image/jpeg"}]
    
    # AI flag
    ai_response_used = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate="now()", nullable=True)
    
    # Relationships
    lead = relationship("Lead", back_populates="chat_messages")
    broker = relationship("Broker")
    
    # Indices para búsquedas comunes
    __table_args__ = (
        # Búsqueda por lead y proveedor
        Index('idx_chat_messages_lead_provider', 'lead_id', 'provider'),
        # Búsqueda por broker y proveedor
        Index('idx_chat_messages_broker_provider', 'broker_id', 'provider'),
        # Búsqueda por canal y usuario
        Index('idx_chat_messages_channel_user', 'provider', 'channel_user_id'),
    )
```

### 2. Configuración por Broker

```python
# backend/app/models/broker_chat_config.py
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.chat_message import ChatProvider

class BrokerChatConfig(Base, IdMixin, TimestampMixin):
    """Chat configuration for broker - supports multiple providers"""
    
    __tablename__ = "broker_chat_configs"
    
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Proveedores habilitados
    enabled_providers = Column(JSONB, default=[], nullable=False)
    # Ejemplo: ["telegram", "whatsapp", "instagram"]
    
    # Proveedor por defecto
    default_provider = Column(
        SQLEnum(ChatProvider),
        default=ChatProvider.WEBCHAT,
        nullable=False
    )
    
    # Credenciales por proveedor (JSONB para flexibilidad)
    provider_configs = Column(JSONB, nullable=True)
    # Estructura:
    # {
    #   "telegram": {
    #     "bot_token": "xxx",
    #     "webhook_secret": "yyy"
    #   },
    #   "whatsapp": {
    #     "phone_number_id": "123",
    #     "access_token": "xxx",
    #     "verify_token": "yyy",
    #     "business_account_id": "zzz"
    #   },
    #   "instagram": {
    #     "page_id": "123",
    #     "page_access_token": "xxx"
    #   }
    # }
    
    # Webhooks por proveedor
    webhook_configs = Column(JSONB, nullable=True)
    # {
    #   "telegram": {"url": "https://...", "enabled": true},
    #   "whatsapp": {"url": "https://...", "enabled": true, "verify_token": "..."}
    # }
    
    # Configuración de características
    features = Column(JSONB, nullable=True)
    # {
    #   "auto_reply": true,
    #   "typing_indicator": true,
    #   "read_receipts": true,
    #   "message_templates": {...},
    #   "business_hours": {...}
    # }
    
    # Rate limiting por proveedor
    rate_limits = Column(JSONB, nullable=True)
    # {
    #   "telegram": {"messages_per_second": 30},
    #   "whatsapp": {"messages_per_second": 60}
    # }
    
    broker = relationship("Broker", back_populates="chat_config")
```

### 3. Interface de Chat Provider (Abstract)

```python
# backend/app/services/chat/base_provider.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

@dataclass
class ChatMessageData:
    """Datos normalizados de mensaje para cualquier proveedor"""
    channel_user_id: str
    channel_username: Optional[str]
    channel_message_id: Optional[str]
    message_text: str
    direction: str  # "in" or "out"
    provider_metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None

@dataclass
class SendMessageResult:
    """Resultado de envío de mensaje"""
    success: bool
    message_id: Optional[str]
    error: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None

class BaseChatProvider(ABC):
    """Base class for all chat providers"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration
        
        Args:
            config: Provider-specific configuration (from BrokerChatConfig.provider_configs)
        """
        self.config = config
    
    @abstractmethod
    async def send_message(
        self,
        channel_user_id: str,
        message_text: str,
        **kwargs
    ) -> SendMessageResult:
        """
        Send message to user
        
        Args:
            channel_user_id: User ID in the channel (telegram_id, phone number, etc.)
            message_text: Message content
            **kwargs: Provider-specific options (reply_to, parse_mode, etc.)
        
        Returns:
            SendMessageResult with success status and message_id
        """
        pass
    
    @abstractmethod
    async def send_media(
        self,
        channel_user_id: str,
        media_url: str,
        media_type: str,  # "image", "video", "audio", "document"
        caption: Optional[str] = None,
        **kwargs
    ) -> SendMessageResult:
        """Send media message"""
        pass
    
    @abstractmethod
    async def set_webhook(self, webhook_url: str, **kwargs) -> Dict[str, Any]:
        """Configure webhook for receiving messages"""
        pass
    
    @abstractmethod
    async def delete_webhook(self) -> Dict[str, Any]:
        """Remove webhook configuration"""
        pass
    
    @abstractmethod
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get current webhook configuration"""
        pass
    
    @abstractmethod
    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        """
        Parse incoming webhook payload into normalized ChatMessageData
        
        Args:
            payload: Raw webhook payload from provider
        
        Returns:
            ChatMessageData if valid message, None otherwise
        """
        pass
    
    @abstractmethod
    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify webhook signature for security
        
        Args:
            payload: Webhook payload
            signature: Signature from provider (usually in headers)
        
        Returns:
            True if signature is valid
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name (telegram, whatsapp, etc.)"""
        pass
```

### 4. Implementación de Telegram Provider

```python
# backend/app/services/chat/telegram_provider.py
import httpx
import logging
from typing import Optional, Dict, Any
from app.services.chat.base_provider import (
    BaseChatProvider,
    ChatMessageData,
    SendMessageResult
)

logger = logging.getLogger(__name__)

class TelegramProvider(BaseChatProvider):
    """Telegram Bot API provider implementation"""
    
    BASE_URL = "https://api.telegram.org"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get("bot_token")
        if not self.bot_token:
            raise ValueError("Telegram bot_token is required")
        self.api_url = f"{self.BASE_URL}/bot{self.bot_token}"
        self.webhook_secret = config.get("webhook_secret")
    
    async def send_message(
        self,
        channel_user_id: str,
        message_text: str,
        **kwargs
    ) -> SendMessageResult:
        """Send text message via Telegram"""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": int(channel_user_id),
                    "text": message_text,
                    "parse_mode": kwargs.get("parse_mode", "HTML")
                }
                
                # Optional reply_to
                if reply_to := kwargs.get("reply_to_message_id"):
                    payload["reply_to_message_id"] = reply_to
                
                response = await client.post(
                    f"{self.api_url}/sendMessage",
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message_id = str(result["result"]["message_id"])
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Telegram send failed: {error_text}")
                    return SendMessageResult(
                        success=False,
                        message_id=None,
                        error=error_text
                    )
        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}", exc_info=True)
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e)
            )
    
    async def send_media(
        self,
        channel_user_id: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        **kwargs
    ) -> SendMessageResult:
        """Send media via Telegram"""
        try:
            # Map media_type to Telegram API method
            method_map = {
                "image": "sendPhoto",
                "video": "sendVideo",
                "audio": "sendAudio",
                "document": "sendDocument"
            }
            
            method = method_map.get(media_type, "sendDocument")
            field_map = {
                "image": "photo",
                "video": "video",
                "audio": "audio",
                "document": "document"
            }
            field = field_map.get(media_type, "document")
            
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": int(channel_user_id),
                    field: media_url
                }
                
                if caption:
                    payload["caption"] = caption
                
                response = await client.post(
                    f"{self.api_url}/{method}",
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message_id = str(result["result"]["message_id"])
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result
                    )
                else:
                    return SendMessageResult(
                        success=False,
                        message_id=None,
                        error=await response.text()
                    )
        
        except Exception as e:
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e)
            )
    
    async def set_webhook(self, webhook_url: str, **kwargs) -> Dict[str, Any]:
        """Set Telegram webhook"""
        async with httpx.AsyncClient() as client:
            payload = {"url": webhook_url}
            
            if self.webhook_secret:
                payload["secret_token"] = self.webhook_secret
            
            response = await client.post(
                f"{self.api_url}/setWebhook",
                json=payload
            )
            
            return response.json()
    
    async def delete_webhook(self) -> Dict[str, Any]:
        """Delete Telegram webhook"""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.api_url}/deleteWebhook")
            return response.json()
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get Telegram webhook info"""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.api_url}/getWebhookInfo")
            return response.json()
    
    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        """
        Parse Telegram webhook payload
        
        Telegram webhook structure:
        {
            "update_id": 123,
            "message": {
                "message_id": 456,
                "from": {"id": 789, "username": "user", ...},
                "chat": {"id": 789, ...},
                "text": "Hello",
                "date": 1234567890
            }
        }
        """
        message = payload.get("message")
        if not message:
            return None
        
        from_user = message.get("from", {})
        
        return ChatMessageData(
            channel_user_id=str(from_user.get("id")),
            channel_username=from_user.get("username"),
            channel_message_id=str(message.get("message_id")),
            message_text=message.get("text", ""),
            direction="in",
            provider_metadata={
                "chat_id": message.get("chat", {}).get("id"),
                "message_type": "text" if message.get("text") else "other",
                "date": message.get("date"),
                "from": from_user
            },
            attachments=self._extract_attachments(message)
        )
    
    def _extract_attachments(self, message: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract media attachments from Telegram message"""
        attachments = []
        
        # Check for different media types
        for media_type in ["photo", "video", "audio", "document", "voice", "sticker"]:
            if media_type in message:
                media = message[media_type]
                # Photo is an array, take the largest
                if media_type == "photo":
                    media = media[-1] if isinstance(media, list) else media
                
                attachments.append({
                    "type": media_type,
                    "file_id": media.get("file_id"),
                    "file_size": media.get("file_size"),
                    "mime_type": media.get("mime_type")
                })
        
        return attachments if attachments else None
    
    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify Telegram webhook signature
        Telegram uses secret_token in header: X-Telegram-Bot-Api-Secret-Token
        """
        if not self.webhook_secret:
            # If no secret configured, skip verification (not recommended for production)
            return True
        
        return signature == self.webhook_secret
    
    def get_provider_name(self) -> str:
        return "telegram"
```

### 5. Implementación de WhatsApp Provider (Meta)

```python
# backend/app/services/chat/whatsapp_provider.py
import httpx
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from app.services.chat.base_provider import (
    BaseChatProvider,
    ChatMessageData,
    SendMessageResult
)

logger = logging.getLogger(__name__)

class WhatsAppProvider(BaseChatProvider):
    """WhatsApp Business API provider (Meta)"""
    
    BASE_URL = "https://graph.facebook.com"
    API_VERSION = "v18.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.phone_number_id = config.get("phone_number_id")
        self.access_token = config.get("access_token")
        self.verify_token = config.get("verify_token")
        self.app_secret = config.get("app_secret")  # For webhook verification
        
        if not all([self.phone_number_id, self.access_token]):
            raise ValueError("WhatsApp phone_number_id and access_token are required")
        
        self.api_url = f"{self.BASE_URL}/{self.API_VERSION}/{self.phone_number_id}"
    
    async def send_message(
        self,
        channel_user_id: str,
        message_text: str,
        **kwargs
    ) -> SendMessageResult:
        """Send text message via WhatsApp"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": channel_user_id,  # Phone number in international format
                "type": "text",
                "text": {
                    "preview_url": kwargs.get("preview_url", False),
                    "body": message_text
                }
            }
            
            # Optional context (reply to message)
            if context_message_id := kwargs.get("context_message_id"):
                payload["context"] = {
                    "message_id": context_message_id
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/messages",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message_id = result["messages"][0]["id"]
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result
                    )
                else:
                    error = await response.text()
                    logger.error(f"WhatsApp send failed: {error}")
                    return SendMessageResult(
                        success=False,
                        message_id=None,
                        error=error
                    )
        
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}", exc_info=True)
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e)
            )
    
    async def send_media(
        self,
        channel_user_id: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        **kwargs
    ) -> SendMessageResult:
        """Send media via WhatsApp"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Map generic media_type to WhatsApp type
            type_map = {
                "image": "image",
                "video": "video",
                "audio": "audio",
                "document": "document"
            }
            wa_type = type_map.get(media_type, "document")
            
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": channel_user_id,
                "type": wa_type,
                wa_type: {
                    "link": media_url
                }
            }
            
            # Add caption if supported and provided
            if caption and wa_type in ["image", "video", "document"]:
                payload[wa_type]["caption"] = caption
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/messages",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message_id = result["messages"][0]["id"]
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result
                    )
                else:
                    return SendMessageResult(
                        success=False,
                        message_id=None,
                        error=await response.text()
                    )
        
        except Exception as e:
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e)
            )
    
    async def set_webhook(self, webhook_url: str, **kwargs) -> Dict[str, Any]:
        """
        Configure WhatsApp webhook
        Note: WhatsApp webhooks are configured at the App level in Meta Business Suite
        This method just returns info about the process
        """
        return {
            "message": "WhatsApp webhooks must be configured in Meta Business Suite",
            "steps": [
                "Go to Meta Business Suite",
                "Select your app",
                "Configure Webhooks with callback URL and verify token",
                "Subscribe to 'messages' webhook"
            ],
            "webhook_url": webhook_url,
            "verify_token": self.verify_token
        }
    
    async def delete_webhook(self) -> Dict[str, Any]:
        """WhatsApp webhooks are managed in Meta Business Suite"""
        return {"message": "Manage webhooks in Meta Business Suite"}
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """WhatsApp webhooks are managed in Meta Business Suite"""
        return {"message": "Check webhook configuration in Meta Business Suite"}
    
    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        """
        Parse WhatsApp webhook payload
        
        WhatsApp webhook structure:
        {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "BUSINESS_ACCOUNT_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "123"},
                        "messages": [{
                            "from": "5491112345678",
                            "id": "wamid.XXX",
                            "timestamp": "1234567890",
                            "text": {"body": "Hello"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            
            if not messages:
                return None
            
            message = messages[0]
            message_type = message.get("type")
            
            # Extract text based on message type
            message_text = ""
            if message_type == "text":
                message_text = message.get("text", {}).get("body", "")
            elif message_type == "button":
                message_text = message.get("button", {}).get("text", "")
            elif message_type == "interactive":
                interactive = message.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    message_text = interactive.get("button_reply", {}).get("title", "")
                elif interactive.get("type") == "list_reply":
                    message_text = interactive.get("list_reply", {}).get("title", "")
            
            return ChatMessageData(
                channel_user_id=message.get("from"),
                channel_username=None,  # WhatsApp doesn't provide username
                channel_message_id=message.get("id"),
                message_text=message_text,
                direction="in",
                provider_metadata={
                    "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
                    "message_type": message_type,
                    "timestamp": message.get("timestamp"),
                    "context": message.get("context")  # If replying to a message
                },
                attachments=self._extract_attachments(message)
            )
        
        except Exception as e:
            logger.error(f"Error parsing WhatsApp webhook: {e}", exc_info=True)
            return None
    
    def _extract_attachments(self, message: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract media attachments from WhatsApp message"""
        message_type = message.get("type")
        
        if message_type in ["image", "video", "audio", "document", "sticker"]:
            media = message.get(message_type, {})
            return [{
                "type": message_type,
                "id": media.get("id"),
                "mime_type": media.get("mime_type"),
                "sha256": media.get("sha256"),
                "caption": media.get("caption")
            }]
        
        return None
    
    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify WhatsApp webhook signature using app_secret
        Signature is sent in X-Hub-Signature-256 header
        Format: sha256=<signature>
        """
        if not self.app_secret:
            logger.warning("WhatsApp app_secret not configured, skipping signature verification")
            return True
        
        try:
            # Remove 'sha256=' prefix if present
            signature = signature.replace("sha256=", "")
            
            # Calculate expected signature
            import json
            payload_str = json.dumps(payload, separators=(',', ':'))
            expected_signature = hmac.new(
                self.app_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        
        except Exception as e:
            logger.error(f"Error verifying WhatsApp signature: {e}", exc_info=True)
            return False
    
    def get_provider_name(self) -> str:
        return "whatsapp"
```

### 6. Factory de Chat Providers

```python
# backend/app/services/chat/factory.py
from typing import Dict, Any
from app.services.chat.base_provider import BaseChatProvider
from app.services.chat.telegram_provider import TelegramProvider
from app.services.chat.whatsapp_provider import WhatsAppProvider
from app.models.chat_message import ChatProvider

class ChatProviderFactory:
    """Factory for creating chat provider instances"""
    
    _providers = {
        ChatProvider.TELEGRAM.value: TelegramProvider,
        ChatProvider.WHATSAPP.value: WhatsAppProvider,
        # Future providers:
        # ChatProvider.INSTAGRAM.value: InstagramProvider,
        # ChatProvider.FACEBOOK.value: FacebookProvider,
        # ChatProvider.TIKTOK.value: TikTokProvider,
    }
    
    @classmethod
    def create(cls, provider_name: str, config: Dict[str, Any]) -> BaseChatProvider:
        """
        Create chat provider instance
        
        Args:
            provider_name: Name of provider (telegram, whatsapp, etc.)
            config: Provider configuration dict
        
        Returns:
            BaseChatProvider instance
        
        Raises:
            ValueError: If provider not supported
        """
        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unsupported chat provider: {provider_name}")
        
        return provider_class(config)
    
    @classmethod
    def register_provider(cls, provider_name: str, provider_class: type):
        """Register custom chat provider"""
        cls._providers[provider_name] = provider_class
    
    @classmethod
    def get_supported_providers(cls) -> list:
        """Get list of supported provider names"""
        return list(cls._providers.keys())
```

### 7. Servicio de Chat Orquestador Actualizado

```python
# backend/app/services/chat_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import logging
from app.services.chat.factory import ChatProviderFactory
from app.services.chat.base_provider import ChatMessageData, SendMessageResult
from app.models.chat_message import ChatMessage, MessageDirection, MessageStatus
from app.models.broker_chat_config import BrokerChatConfig

logger = logging.getLogger(__name__)

class ChatService:
    """Service for managing chat messages across providers"""
    
    @staticmethod
    async def get_broker_chat_config(
        db: AsyncSession,
        broker_id: int
    ) -> Optional[BrokerChatConfig]:
        """Get chat configuration for broker"""
        from sqlalchemy.future import select
        
        result = await db.execute(
            select(BrokerChatConfig).where(BrokerChatConfig.broker_id == broker_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_provider_for_broker(
        db: AsyncSession,
        broker_id: int,
        provider_name: str
    ) -> Optional[BaseChatProvider]:
        """Get chat provider instance for broker"""
        config = await ChatService.get_broker_chat_config(db, broker_id)
        if not config:
            logger.warning(f"No chat config found for broker {broker_id}")
            return None
        
        # Check if provider is enabled
        if provider_name not in config.enabled_providers:
            logger.warning(f"Provider {provider_name} not enabled for broker {broker_id}")
            return None
        
        # Get provider config
        provider_configs = config.provider_configs or {}
        provider_config = provider_configs.get(provider_name)
        
        if not provider_config:
            logger.warning(f"No config found for provider {provider_name}")
            return None
        
        # Create provider instance
        try:
            provider = ChatProviderFactory.create(provider_name, provider_config)
            return provider
        except Exception as e:
            logger.error(f"Error creating provider {provider_name}: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def send_message(
        db: AsyncSession,
        broker_id: int,
        provider_name: str,
        channel_user_id: str,
        message_text: str,
        lead_id: Optional[int] = None,
        **kwargs
    ) -> SendMessageResult:
        """
        Send message via specified provider
        
        Args:
            db: Database session
            broker_id: Broker ID
            provider_name: Provider name (telegram, whatsapp, etc.)
            channel_user_id: User ID in the channel
            message_text: Message content
            lead_id: Optional lead ID for logging
            **kwargs: Provider-specific options
        
        Returns:
            SendMessageResult
        """
        provider = await ChatService.get_provider_for_broker(db, broker_id, provider_name)
        if not provider:
            return SendMessageResult(
                success=False,
                message_id=None,
                error=f"Provider {provider_name} not available"
            )
        
        # Send message
        result = await provider.send_message(channel_user_id, message_text, **kwargs)
        
        # Log message to database if successful and lead_id provided
        if result.success and lead_id:
            await ChatService.log_message(
                db=db,
                lead_id=lead_id,
                broker_id=broker_id,
                provider_name=provider_name,
                message_data=ChatMessageData(
                    channel_user_id=channel_user_id,
                    channel_username=None,
                    channel_message_id=result.message_id,
                    message_text=message_text,
                    direction="out",
                    provider_metadata=result.provider_response
                ),
                status=MessageStatus.SENT
            )
        
        return result
    
    @staticmethod
    async def log_message(
        db: AsyncSession,
        lead_id: int,
        broker_id: int,
        provider_name: str,
        message_data: ChatMessageData,
        status: MessageStatus = MessageStatus.SENT,
        ai_used: bool = True
    ) -> ChatMessage:
        """Log chat message to database"""
        from app.models.chat_message import ChatProvider
        
        message = ChatMessage(
            lead_id=lead_id,
            broker_id=broker_id,
            provider=ChatProvider(provider_name),
            channel_user_id=message_data.channel_user_id,
            channel_username=message_data.channel_username,
            channel_message_id=message_data.channel_message_id,
            message_text=message_data.message_text,
            direction=MessageDirection.INBOUND if message_data.direction == "in" else MessageDirection.OUTBOUND,
            status=status,
            provider_metadata=message_data.provider_metadata,
            attachments=message_data.attachments,
            ai_response_used=ai_used
        )
        
        db.add(message)
        await db.commit()
        await db.refresh(message)
        
        return message
    
    @staticmethod
    async def handle_webhook(
        db: AsyncSession,
        broker_id: int,
        provider_name: str,
        payload: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Optional[ChatMessage]:
        """
        Handle incoming webhook from provider
        
        Args:
            db: Database session
            broker_id: Broker ID
            provider_name: Provider name
            payload: Webhook payload
            signature: Optional signature for verification
        
        Returns:
            ChatMessage if processed successfully, None otherwise
        """
        provider = await ChatService.get_provider_for_broker(db, broker_id, provider_name)
        if not provider:
            logger.error(f"Provider {provider_name} not available for broker {broker_id}")
            return None
        
        # Verify signature if provided
        if signature:
            is_valid = await provider.verify_webhook_signature(payload, signature)
            if not is_valid:
                logger.error(f"Invalid webhook signature for {provider_name}")
                return None
        
        # Parse message
        message_data = await provider.parse_webhook_message(payload)
        if not message_data:
            logger.debug(f"No message data extracted from webhook")
            return None
        
        # Find or create lead
        from app.services.lead_service import LeadService
        from app.schemas.lead import LeadCreate
        
        # Try to find lead by channel_user_id
        lead = await LeadService.find_lead_by_channel(
            db,
            provider_name,
            message_data.channel_user_id
        )
        
        if not lead:
            # Create new lead
            lead_data = LeadCreate(
                phone=message_data.channel_user_id if provider_name == "whatsapp" else f"{provider_name}_{message_data.channel_user_id}",
                name=message_data.channel_username or "New Contact",
                tags=[provider_name, "inbound"],
            )
            lead = await LeadService.create_lead(db, lead_data, broker_id=broker_id)
        
        # Log message
        chat_message = await ChatService.log_message(
            db=db,
            lead_id=lead.id,
            broker_id=broker_id,
            provider_name=provider_name,
            message_data=message_data,
            status=MessageStatus.DELIVERED,
            ai_used=False  # Inbound message
        )
        
        return chat_message
```

## 🔄 Plan de Migración

### Fase 1: Preparación (Sin Impacto)
1. Crear nuevos modelos (`ChatMessage`, `BrokerChatConfig`)
2. Crear migración de base de datos
3. Implementar interfaces y providers
4. Mantener compatibilidad con `TelegramMessage`

### Fase 2: Migración Gradual
1. Migrar datos de `telegram_messages` a `chat_messages`
2. Actualizar `ChatOrchestratorService` para usar nuevo sistema
3. Actualizar rutas para soportar ambos modelos
4. Testing exhaustivo

### Fase 3: Limpieza
1. Deprecar `TelegramMessage` (mantener solo para referencia)
2. Actualizar documentación
3. Migrar configuraciones a `BrokerChatConfig`

## 📊 Comparación: Antes vs Después

### Antes (Acoplado)
```python
# ❌ Acoplado a Telegram
telegram_service = TelegramService(token=settings.TELEGRAM_TOKEN)
await telegram_service.send_message(chat_id=123, text="Hello")

# ❌ Modelo específico
message = TelegramMessage(
    telegram_user_id=123,
    telegram_message_id="456",
    message_text="Hello"
)
```

### Después (Desacoplado)
```python
# ✅ Proveedor agnóstico
provider = await ChatService.get_provider_for_broker(db, broker_id, "telegram")
await provider.send_message(channel_user_id="123", message_text="Hello")

# O mejor aún, usar el servicio directamente
await ChatService.send_message(
    db=db,
    broker_id=1,
    provider_name="whatsapp",  # Fácil cambiar a cualquier proveedor
    channel_user_id="+5491112345678",
    message_text="Hello",
    lead_id=123
)

# ✅ Modelo genérico
message = ChatMessage(
    provider=ChatProvider.WHATSAPP,
    channel_user_id="+5491112345678",
    message_text="Hello"
)
```

## 🎯 Beneficios de la Arquitectura

1. **Escalabilidad**: Agregar nuevos proveedores es trivial
2. **Mantenibilidad**: Cada provider es independiente
3. **Testabilidad**: Fácil crear mocks de providers
4. **Configurabilidad**: Cada broker puede tener diferentes proveedores
5. **Flexibilidad**: Cambiar entre proveedores sin cambiar código
6. **Seguridad**: Credenciales por broker, no globales
7. **Multi-tenancy**: Soporta múltiples brokers con diferentes configuraciones

## 🚀 Próximos Pasos

1. **Revisar y aprobar arquitectura**
2. **Crear migración de base de datos**
3. **Implementar providers base (Telegram, WhatsApp)**
4. **Actualizar ChatOrchestratorService**
5. **Testing e integración**
6. **Documentación de uso**

## 📚 Referencias

- [WhatsApp Business API Docs](https://developers.facebook.com/docs/whatsapp)
- [Telegram Bot API Docs](https://core.telegram.org/bots/api)
- [Instagram Messaging API](https://developers.facebook.com/docs/messenger-platform)
- [Facebook Messenger Platform](https://developers.facebook.com/docs/messenger-platform)
