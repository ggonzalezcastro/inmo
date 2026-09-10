"""Asset-aware processing for normalized Meta messaging events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import ws_manager
from app.models.activity_log import ActivityLog
from app.models.chat_message import ChatMessage, ChatProvider, MessageDirection, MessageStatus
from app.models.lead import Lead, LeadStatus
from app.models.meta import ChannelIdentity, MetaAsset, MetaAssignmentConflict
from app.models.user import User
from app.services.chat.base_provider import ChatMessageData
from app.services.chat.orchestrator import ChatOrchestratorService
from app.services.chat.service import ChatService
from app.services.conversations.conversation_service import ConversationService
from app.services.leads import LeadService
from app.services.leads.assignment_service import LeadAssignmentService
from app.services.meta.normalization import NormalizedMetaMessage, NormalizedMetaStatus
from app.services.meta.resolver import MetaAssetResolver
from app.services.meta.feature_flags import MetaFeatureFlagService


AUTO_SEND_BLOCKED_PATTERNS = (
    "aprobación garantizada",
    "credito garantizado",
    "crédito garantizado",
    "sin dicom",
)


def _auto_send_block_reason(event: NormalizedMetaMessage, result) -> Optional[str]:
    if not (event.text or "").strip():
        return "message_without_text"
    metadata = result.metadata or {}
    if metadata.get("requires_human") is True:
        return "agent_requested_handoff"
    confidence = metadata.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < 0.75:
        return "low_confidence"
    normalized = (result.response or "").lower()
    if any(pattern in normalized for pattern in AUTO_SEND_BLOCKED_PATTERNS):
        return "unsafe_financial_claim"
    return None


class MetaInboundMessageService:
    @staticmethod
    async def _resolve_or_create_lead(
        db: AsyncSession,
        *,
        broker_id: int,
        asset: MetaAsset,
        event: NormalizedMetaMessage,
    ) -> tuple[Lead, ChannelIdentity, bool]:
        identity = await db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.broker_id == broker_id,
                ChannelIdentity.asset_id == asset.id,
                ChannelIdentity.channel == event.provider,
                ChannelIdentity.external_user_id == event.sender_id,
            )
        )
        if identity and identity.lead_id:
            lead = await db.scalar(
                select(Lead).where(Lead.id == identity.lead_id, Lead.broker_id == broker_id)
            )
            if lead:
                identity.last_interaction_at = datetime.now(timezone.utc)
                return lead, identity, False

        lead: Optional[Lead] = None
        ambiguous = False
        if event.provider == "whatsapp":
            normalized_phone = LeadService.normalize_phone(event.sender_id)
            candidates = list((await db.scalars(
                select(Lead).where(
                    Lead.broker_id == broker_id,
                    Lead.phone == normalized_phone,
                ).limit(2)
            )).all())
            if len(candidates) == 1:
                lead = candidates[0]
            elif len(candidates) > 1:
                ambiguous = True

        created = False
        if lead is None:
            phone = (
                LeadService.normalize_phone(event.sender_id)
                if event.provider == "whatsapp"
                else None
            )
            tags = [event.provider, "inbound"]
            if ambiguous:
                tags.append("identity_review")
            lead = Lead(
                phone=phone,
                name=event.username or f"Contacto {event.provider.title()}",
                tags=tags,
                lead_metadata={
                    "source": event.provider,
                    "meta_asset_id": asset.id,
                    "identity_review_required": ambiguous,
                },
                status=LeadStatus.COLD,
                lead_score=0.0,
                broker_id=broker_id,
            )
            db.add(lead)
            await db.flush()
            created = True

        if identity is None:
            now = datetime.now(timezone.utc)
            identity = ChannelIdentity(
                broker_id=broker_id,
                asset_id=asset.id,
                lead_id=lead.id,
                channel=event.provider,
                external_user_id=event.sender_id,
                username=event.username,
                display_name=event.username,
                phone=LeadService.normalize_phone(event.sender_id) if event.provider == "whatsapp" else None,
                first_interaction_at=now,
                last_interaction_at=now,
                identity_metadata={"referral": event.metadata.get("referral")},
            )
            db.add(identity)
            await db.flush()
        else:
            identity.lead_id = lead.id
            identity.last_interaction_at = datetime.now(timezone.utc)
        return lead, identity, created

    @staticmethod
    async def _apply_assignment(
        db: AsyncSession,
        *,
        lead: Lead,
        asset: MetaAsset,
        is_new: bool,
    ) -> None:
        asset_agent = asset.assigned_user_id or asset.owner_user_id
        if asset_agent:
            active_agent = await db.scalar(
                select(User).where(
                    User.id == asset_agent,
                    User.broker_id == lead.broker_id,
                    User.is_active.is_(True),
                )
            )
            if not active_agent:
                asset_agent = None
        if is_new and asset_agent:
            lead.assigned_to = asset_agent
            db.add(ActivityLog(
                lead_id=lead.id,
                action_type="agent_assigned",
                details={
                    "old_agent_id": None,
                    "new_agent_id": asset_agent,
                    "assigned_by": "system",
                    "reason": "meta_asset_owner",
                    "meta_asset_id": asset.id,
                },
                timestamp=datetime.now(timezone.utc),
            ))
            await db.commit()
            await ws_manager.broadcast(lead.broker_id, "lead_assigned", {
                "lead_id": lead.id,
                "agent_id": asset_agent,
                "reason": "meta_asset_owner",
                "meta_asset_id": asset.id,
            })
            return
        if is_new and not asset_agent:
            await LeadAssignmentService.assign_automatically(
                db,
                lead=lead,
                reason="meta_inbound_general_asset",
            )
            return
        if lead.assigned_to and asset_agent and lead.assigned_to != asset_agent:
            existing = await db.scalar(
                select(MetaAssignmentConflict).where(
                    MetaAssignmentConflict.lead_id == lead.id,
                    MetaAssignmentConflict.asset_id == asset.id,
                    MetaAssignmentConflict.status == "open",
                )
            )
            created_conflict = False
            if not existing:
                existing = MetaAssignmentConflict(
                    broker_id=lead.broker_id,
                    lead_id=lead.id,
                    asset_id=asset.id,
                    current_assignee_id=lead.assigned_to,
                    asset_owner_id=asset_agent,
                    status="open",
                )
                db.add(existing)
                await db.flush()
                created_conflict = True
            await db.commit()
            if created_conflict:
                await ws_manager.broadcast(lead.broker_id, "meta_assignment_conflict", {
                    "conflict_id": existing.id,
                    "lead_id": lead.id,
                    "asset_id": asset.id,
                    "current_assignee_id": lead.assigned_to,
                    "asset_owner_id": asset_agent,
                })

    @staticmethod
    async def process(
        db: AsyncSession,
        event: NormalizedMetaMessage,
    ) -> Optional[ChatMessage]:
        resolved = await MetaAssetResolver.by_external_id(
            db,
            asset_type=event.asset_type,
            external_id=event.asset_external_id,
            require_capability="messaging",
        )
        feature = "messenger" if event.provider == "facebook" else event.provider
        feature_state = await MetaFeatureFlagService.effective(db, resolved.broker_id)
        if not feature_state["channels"].get(feature, False):
            return None
        try:
            provider_enum = ChatProvider(event.provider)
        except ValueError:
            return None
        duplicate = await db.scalar(
            select(ChatMessage.id).where(
                ChatMessage.broker_id == resolved.broker_id,
                ChatMessage.meta_asset_id == resolved.asset_id,
                ChatMessage.provider == provider_enum,
                ChatMessage.channel_message_id == event.message_id,
            )
        )
        if duplicate:
            return None
        asset = await db.scalar(
            select(MetaAsset).where(
                MetaAsset.id == resolved.asset_id,
                MetaAsset.broker_id == resolved.broker_id,
            )
        )
        if not asset:
            return None
        lead, identity, created = await MetaInboundMessageService._resolve_or_create_lead(
            db,
            broker_id=resolved.broker_id,
            asset=asset,
            event=event,
        )
        await MetaInboundMessageService._apply_assignment(
            db,
            lead=lead,
            asset=asset,
            is_new=created,
        )
        conversation = await ConversationService.get_or_create(
            db,
            lead_id=lead.id,
            broker_id=resolved.broker_id,
            channel=event.provider,
            meta_asset_id=asset.id,
            channel_identity_id=identity.id,
        )
        conversation.messaging_window_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        if lead.assigned_to and (asset.assigned_user_id or asset.owner_user_id) not in {None, lead.assigned_to}:
            conversation.assignment_conflict = True
        inbound = await ChatService.log_message(
            db,
            lead_id=lead.id,
            broker_id=resolved.broker_id,
            provider_name=event.provider,
            message_data=ChatMessageData(
                channel_user_id=event.sender_id,
                channel_username=event.username,
                channel_message_id=event.message_id,
                message_text=event.text,
                direction="in",
                provider_metadata=event.metadata,
                attachments=event.attachments,
            ),
            status=MessageStatus.DELIVERED,
            ai_used=False,
            conversation_id=conversation.id,
            meta_asset_id=asset.id,
            generation_mode="manual",
            message_type=event.message_type,
        )
        await ConversationService.on_message(db, conversation.id, inbound.id)
        referral = event.metadata.get("referral")
        if referral:
            from app.services.meta.lead_ads import MetaAttributionService

            await MetaAttributionService.capture_message_referral(
                db,
                lead=lead,
                identity=identity,
                conversation=conversation,
                referral=referral,
            )
        await db.commit()
        await ws_manager.broadcast(resolved.broker_id, "meta_message_received", {
            "conversation_id": conversation.id,
            "lead_id": lead.id,
            "message_id": inbound.id,
            "channel": event.provider,
            "asset_id": asset.id,
            "assigned_to": lead.assigned_to,
        })

        if (
            asset.ai_mode != "supervised_auto"
            or lead.human_mode
            or conversation.assignment_conflict
        ):
            return inbound
        result = await ChatOrchestratorService.process_chat_message(
            db=db,
            current_user={"broker_id": resolved.broker_id, "id": None},
            message=event.text,
            lead_id=lead.id,
            provider_name=event.provider,
            skip_inbound_log=True,
            conversation_id=conversation.id,
            meta_asset_id=asset.id,
            channel_identity_id=identity.id,
            channel_user_id=event.sender_id,
            skip_outbound_log=True,
        )
        if not result.response or result.response == "[human_mode]":
            return inbound
        block_reason = _auto_send_block_reason(event, result)
        if block_reason:
            lead.human_mode = True
            lead.human_assigned_to = lead.assigned_to
            lead.human_taken_at = datetime.now(timezone.utc)
            await ConversationService.set_human_mode(
                db,
                conversation.id,
                True,
                assigned_to=lead.assigned_to,
            )
            await db.commit()
            await ws_manager.broadcast(resolved.broker_id, "meta_ai_handoff_required", {
                "conversation_id": conversation.id,
                "lead_id": lead.id,
                "assigned_to": lead.assigned_to,
                "reason": block_reason,
            })
            return inbound
        from app.services.meta.outbound import MetaOutboundService

        outbound = await MetaOutboundService.send_for_conversation(
            db,
            broker_id=resolved.broker_id,
            conversation_id=conversation.id,
            message_text=result.response,
            sent_by_user_id=None,
            generation_mode="ai_auto",
        )
        if not outbound.provider_result.success:
            raise RuntimeError(outbound.provider_result.error or "Meta outbound send failed")
        return inbound


class MetaMessageStatusService:
    @staticmethod
    async def process(db: AsyncSession, event: NormalizedMetaStatus) -> None:
        resolved = await MetaAssetResolver.by_external_id(
            db,
            asset_type=event.asset_type,
            external_id=event.asset_external_id,
        )
        feature = "messenger" if event.provider == "facebook" else event.provider
        feature_state = await MetaFeatureFlagService.effective(db, resolved.broker_id)
        if not feature_state["channels"].get(feature, False):
            return
        provider = ChatProvider(event.provider)
        watermark = event.metadata.get("watermark")
        sender_id = str(event.metadata.get("sender_id") or "")
        if event.status == "read" and watermark and sender_id:
            try:
                read_at = datetime.fromtimestamp(int(watermark) / 1000, tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                return
            recent = await db.scalar(select(ChatMessage).where(
                ChatMessage.broker_id == resolved.broker_id,
                ChatMessage.meta_asset_id == resolved.asset_id,
                ChatMessage.provider == provider,
                ChatMessage.channel_user_id == sender_id,
                ChatMessage.direction == MessageDirection.OUTBOUND,
                ChatMessage.created_at <= read_at,
            ).order_by(ChatMessage.id.desc()).limit(1))
            await db.execute(update(ChatMessage).where(
                ChatMessage.broker_id == resolved.broker_id,
                ChatMessage.meta_asset_id == resolved.asset_id,
                ChatMessage.provider == provider,
                ChatMessage.channel_user_id == sender_id,
                ChatMessage.direction == MessageDirection.OUTBOUND,
                ChatMessage.created_at <= read_at,
                ChatMessage.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
            ).values(status=MessageStatus.READ))
            await db.commit()
            if recent:
                await ws_manager.broadcast(resolved.broker_id, "meta_message_status_changed", {
                    "message_id": recent.id,
                    "conversation_id": recent.conversation_id,
                    "status": "read",
                })
            return
        message = await db.scalar(
            select(ChatMessage).where(
                ChatMessage.broker_id == resolved.broker_id,
                ChatMessage.meta_asset_id == resolved.asset_id,
                ChatMessage.provider == provider,
                ChatMessage.channel_message_id == event.message_id,
            )
        )
        if not message:
            return
        mapped = {
            "sent": MessageStatus.SENT,
            "delivered": MessageStatus.DELIVERED,
            "read": MessageStatus.READ,
            "failed": MessageStatus.FAILED,
        }.get(event.status)
        if mapped:
            message.status = mapped
        message.remote_error_code = event.error_code
        message.remote_error_subcode = event.error_subcode
        await db.commit()
        await ws_manager.broadcast(resolved.broker_id, "meta_message_status_changed", {
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "status": event.status,
        })
