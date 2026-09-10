"""Single asset-aware outbound path for human, AI, referral, and campaigns."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import ws_manager
from app.core.redis_client import get_redis
from app.models.chat_message import ChatMessage, MessageStatus
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.meta import ChannelIdentity, MetaAsset, MetaMessageTemplate
from app.services.chat.base_provider import ChatMessageData, SendMessageResult
from app.services.chat.factory import ChatProviderFactory
from app.services.chat.service import ChatService
from app.services.conversations.conversation_service import ConversationService
from app.services.meta.resolver import MetaAssetResolutionError, MetaAssetResolver
from app.services.meta.feature_flags import MetaFeatureFlagService
from app.services.meta.metrics import record_outbound
from app.services.meta.url_safety import is_public_https_url


class MetaOutboundError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class MetaOutboundResult:
    message: ChatMessage
    provider_result: SendMessageResult


def _aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _enforce_outbound_rate(asset_id: int, external_user_id: str) -> None:
    """Limit one sender/asset pair without blocking all tenants behind an asset."""
    try:
        redis = await get_redis()
        now_bucket = int(datetime.now(timezone.utc).timestamp())
        sender_hash = hashlib.sha256(external_user_id.encode()).hexdigest()[:20]
        minute_key = f"meta:outbound:minute:{asset_id}:{sender_hash}:{now_bucket // 60}"
        burst_key = f"meta:outbound:burst:{asset_id}:{sender_hash}:{now_bucket // 5}"
        pipe = redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 75)
        pipe.incr(burst_key)
        pipe.expire(burst_key, 10)
        minute_count, _, burst_count, _ = await pipe.execute()
        if int(minute_count) > 60 or int(burst_count) > 10:
            raise MetaOutboundError(
                "RATE_LIMITED",
                "Hay demasiados envíos a este contacto; espera unos segundos",
                status_code=429,
            )
    except MetaOutboundError:
        raise
    except Exception:
        # Provider rate limits remain the fallback when Redis is unavailable.
        return


class MetaOutboundService:
    @staticmethod
    async def send_for_conversation(
        db: AsyncSession,
        *,
        broker_id: int,
        conversation_id: int,
        message_text: str,
        sent_by_user_id: Optional[int],
        generation_mode: str = "manual",
        reply_to_external_id: Optional[str] = None,
        template_name: Optional[str] = None,
        template_language: str = "es_CL",
        template_components: Optional[list[dict[str, Any]]] = None,
        media_url: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> MetaOutboundResult:
        text = (message_text or "").strip()
        if not text and not template_name and not media_url:
            raise MetaOutboundError("EMPTY_MESSAGE", "El mensaje no puede estar vacío")
        if len(text) > 4096:
            raise MetaOutboundError("MESSAGE_TOO_LONG", "El mensaje supera 4096 caracteres")
        if bool(media_url) != bool(media_type):
            raise MetaOutboundError(
                "INVALID_MEDIA",
                "La URL y el tipo de adjunto deben enviarse juntos",
            )
        if media_url and not is_public_https_url(media_url):
            raise MetaOutboundError(
                "UNSAFE_MEDIA_URL",
                "El adjunto debe usar una URL HTTPS pública",
            )
        if media_url and template_name:
            raise MetaOutboundError(
                "INVALID_MEDIA_TEMPLATE",
                "No se puede combinar un adjunto con una plantilla",
            )

        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.broker_id == broker_id,
            )
        )
        if not conversation:
            raise MetaOutboundError(
                "CONVERSATION_NOT_FOUND",
                "Conversación no encontrada",
                status_code=404,
            )
        if not conversation.meta_asset_id or not conversation.channel_identity_id:
            raise MetaOutboundError(
                "LEGACY_CONVERSATION",
                "Esta conversación todavía utiliza el canal heredado",
            )
        if conversation.assignment_conflict:
            raise MetaOutboundError(
                "ASSIGNMENT_CONFLICT",
                "Jefatura debe resolver el conflicto de asignación antes de responder",
                status_code=409,
            )

        feature = "messenger" if conversation.channel == "facebook" else conversation.channel
        feature_state = await MetaFeatureFlagService.effective(db, broker_id)
        if not feature_state["channels"].get(feature, False):
            raise MetaOutboundError(
                "CHANNEL_DISABLED",
                "El canal está deshabilitado para este broker",
                status_code=503,
            )

        identity = await db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.id == conversation.channel_identity_id,
                ChannelIdentity.broker_id == broker_id,
                ChannelIdentity.asset_id == conversation.meta_asset_id,
            )
        )
        if not identity:
            raise MetaOutboundError(
                "IDENTITY_NOT_FOUND",
                "No se encontró el destinatario de esta conversación",
                status_code=404,
            )

        try:
            resolved = await MetaAssetResolver.for_conversation(
                db,
                broker_id=broker_id,
                conversation_id=conversation_id,
                require_capability="messaging",
            )
        except MetaAssetResolutionError as exc:
            alternative = await db.scalar(
                select(Conversation.channel)
                .join(MetaAsset, MetaAsset.id == Conversation.meta_asset_id)
                .where(
                    Conversation.broker_id == broker_id,
                    Conversation.lead_id == conversation.lead_id,
                    Conversation.id != conversation.id,
                    Conversation.channel_identity_id.isnot(None),
                    MetaAsset.status == "active",
                    MetaAsset.approval_status == "approved",
                )
                .order_by(Conversation.last_message_at.desc().nullslast())
                .limit(1)
            )
            hint = f" Puedes continuar por {alternative}." if alternative else ""
            raise MetaOutboundError(exc.code, f"{str(exc)}.{hint}", status_code=409) from exc
        await _enforce_outbound_rate(resolved.asset_id, identity.external_user_id)
        if template_name:
            if conversation.channel != "whatsapp":
                raise MetaOutboundError(
                    "TEMPLATE_NOT_SUPPORTED",
                    "Este canal no utiliza plantillas de WhatsApp",
                )
            phone_asset = await db.scalar(
                select(MetaAsset).where(
                    MetaAsset.id == resolved.asset_id,
                    MetaAsset.broker_id == broker_id,
                )
            )
            approved_template = await db.scalar(
                select(MetaMessageTemplate).where(
                    MetaMessageTemplate.broker_id == broker_id,
                    MetaMessageTemplate.connection_id == resolved.connection_id,
                    MetaMessageTemplate.waba_external_id == phone_asset.parent_external_id,
                    MetaMessageTemplate.name == template_name,
                    MetaMessageTemplate.language == template_language,
                    MetaMessageTemplate.status == "APPROVED",
                )
            )
            if not approved_template:
                raise MetaOutboundError(
                    "TEMPLATE_NOT_APPROVED",
                    "La plantilla no está aprobada para este número",
                    status_code=409,
                )
            supplied = {
                str(component.get("type") or "").lower(): component
                for component in (template_components or [])
            }
            for component in approved_template.components or []:
                component_type = str(component.get("type") or "").lower()
                if component_type not in {"header", "body"}:
                    continue
                expected = len(re.findall(r"\{\{\d+\}\}", str(component.get("text") or "")))
                if expected == 0:
                    continue
                parameters = (supplied.get(component_type) or {}).get("parameters") or []
                if len(parameters) != expected or any(
                    not str(parameter.get("text") or "").strip()
                    for parameter in parameters
                ):
                    raise MetaOutboundError(
                        "TEMPLATE_PARAMETERS_INVALID",
                        "Completa todas las variables requeridas por la plantilla",
                        status_code=422,
                    )
        now = datetime.now(timezone.utc)
        window_expires_at = _aware_utc(conversation.messaging_window_expires_at)
        if conversation.channel == "whatsapp" and (
            window_expires_at is None or window_expires_at <= now
        ) and not template_name:
            raise MetaOutboundError(
                "WHATSAPP_TEMPLATE_REQUIRED",
                "La ventana de atención venció; selecciona una plantilla aprobada",
                status_code=409,
            )
        if conversation.channel in {"instagram", "facebook"} and (
            window_expires_at is None or window_expires_at <= now
        ):
            raise MetaOutboundError(
                "POLICY_WINDOW_CLOSED",
                "La ventana de respuesta de Meta está cerrada; espera un nuevo mensaje del contacto",
                status_code=409,
            )

        provider = ChatProviderFactory.create(conversation.channel, {
            "asset_id": resolved.external_id,
            "phone_number_id": resolved.external_id,
            "access_token": resolved.access_token,
        })
        allowed_media = {
            "whatsapp": {"image", "video", "audio", "document"},
            "instagram": {"image", "video"},
            "facebook": {"image", "video", "audio", "document"},
        }
        if media_type and media_type not in allowed_media.get(conversation.channel, set()):
            raise MetaOutboundError(
                "UNSUPPORTED_MEDIA",
                "Este tipo de archivo no está permitido en el canal seleccionado",
            )
        if media_url and media_type:
            result = await provider.send_media(
                identity.external_user_id,
                media_url,
                media_type,
                caption=text or None,
                context_message_id=reply_to_external_id,
            )
        else:
            result = await provider.send_message(
                identity.external_user_id,
                text,
                context_message_id=reply_to_external_id,
                template_name=template_name,
                template_language=template_language,
                template_components=template_components or [],
            )
        status = MessageStatus.SENT if result.success else MessageStatus.FAILED
        record_outbound(
            conversation.channel,
            "template" if template_name else (media_type or "text"),
            "success" if result.success else "failed",
        )
        provider_meta = dict(result.provider_response or {})
        provider_meta["template_name"] = template_name
        message = await ChatService.log_message(
            db,
            lead_id=conversation.lead_id,
            broker_id=broker_id,
            provider_name=conversation.channel,
            message_data=ChatMessageData(
                channel_user_id=identity.external_user_id,
                channel_username=identity.username,
                channel_message_id=result.message_id,
                message_text=text or (f"Plantilla: {template_name}" if template_name else "Adjunto"),
                direction="out",
                provider_metadata=provider_meta,
                attachments=(
                    [{"type": media_type, "url": media_url}]
                    if media_url and media_type
                    else None
                ),
            ),
            status=status,
            ai_used=generation_mode.startswith("ai_"),
            conversation_id=conversation.id,
            meta_asset_id=resolved.asset_id,
            sent_by_user_id=sent_by_user_id,
            generation_mode=generation_mode,
            message_type="template" if template_name else (media_type or "text"),
            reply_to_external_id=reply_to_external_id,
        )
        if not result.success:
            message.remote_error_code = str(provider_meta.get("error_code") or "SEND_FAILED")
            message.remote_error_subcode = (
                str(provider_meta["error_subcode"])
                if provider_meta.get("error_subcode") is not None
                else None
            )
        await ConversationService.on_message(db, conversation.id, message.id)
        await db.commit()
        await ws_manager.broadcast(broker_id, "meta_message_sent", {
            "conversation_id": conversation.id,
            "lead_id": conversation.lead_id,
            "message_id": message.id,
            "channel": conversation.channel,
            "asset_id": resolved.asset_id,
            "status": status.value,
            "generation_mode": generation_mode,
        })
        return MetaOutboundResult(message=message, provider_result=result)

    @staticmethod
    async def conversation_for_lead(
        db: AsyncSession,
        *,
        broker_id: int,
        lead_id: int,
        preferred_channel: Optional[str] = None,
    ) -> Optional[Conversation]:
        filters = [
            Conversation.broker_id == broker_id,
            Conversation.lead_id == lead_id,
            Conversation.meta_asset_id.isnot(None),
            Conversation.channel_identity_id.isnot(None),
            Conversation.status.in_(["active", "human_mode"]),
        ]
        if preferred_channel:
            filters.append(Conversation.channel == preferred_channel)
        return await db.scalar(
            select(Conversation)
            .where(*filters)
            .order_by(
                Conversation.last_message_at.desc().nullslast(),
                Conversation.id.desc(),
            )
            .limit(1)
        )

    @staticmethod
    async def send_for_lead(
        db: AsyncSession,
        *,
        broker_id: int,
        lead_id: int,
        message_text: str,
        generation_mode: str,
        preferred_channel: Optional[str] = None,
        sent_by_user_id: Optional[int] = None,
    ) -> Optional[MetaOutboundResult]:
        lead = await db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.broker_id == broker_id)
        )
        if not lead:
            raise MetaOutboundError("LEAD_NOT_FOUND", "Lead no encontrado", status_code=404)
        conversation = await MetaOutboundService.conversation_for_lead(
            db,
            broker_id=broker_id,
            lead_id=lead_id,
            preferred_channel=preferred_channel,
        )
        if not conversation:
            return None
        return await MetaOutboundService.send_for_conversation(
            db,
            broker_id=broker_id,
            conversation_id=conversation.id,
            message_text=message_text,
            sent_by_user_id=sent_by_user_id,
            generation_mode=generation_mode,
        )
