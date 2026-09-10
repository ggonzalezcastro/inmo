"""Tenant-safe SQL services for the unified Meta conversation inbox."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import and_, desc, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.websocket_manager import ws_manager
from app.models.audit_log import AuditLog
from app.models.chat_message import ChatMessage, MessageDirection
from app.models.conversation import Conversation, ConversationReadState
from app.models.lead import Lead
from app.models.meta import MetaAsset, MetaAssignmentConflict
from app.models.meta_ads import MetaLeadAttribution
from app.models.user import User, UserRole
from app.services.leads.assignment_service import LeadAssignmentService


def user_id_from_claims(current_user: dict) -> int:
    raw = current_user.get("user_id") or current_user.get("id")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Identidad de usuario inválida") from exc


def broker_id_from_claims(current_user: dict) -> int:
    raw = current_user.get("broker_id")
    if raw is None:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")
    return int(raw)


def role_from_claims(current_user: dict) -> str:
    return str(current_user.get("role") or "").upper()


def _encode_cursor(last_at: datetime, conversation_id: int) -> str:
    raw = json.dumps({"at": last_at.isoformat(), "id": conversation_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, int]:
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        at = datetime.fromisoformat(payload["at"])
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        return at, int(payload["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Cursor inválido") from exc


class MetaInboxService:
    @staticmethod
    def _visibility(query, current_user: dict):
        role = role_from_claims(current_user)
        if role == UserRole.AGENT.value:
            uid = user_id_from_claims(current_user)
            return query.where(Lead.assigned_to == uid)
        if role not in {UserRole.ADMIN.value, UserRole.SUPERADMIN.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        return query

    @staticmethod
    async def assert_access(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
        allow_superadmin_send: bool = True,
    ) -> tuple[Conversation, Lead]:
        broker_id = broker_id_from_claims(current_user)
        row = (
            await db.execute(
                select(Conversation, Lead)
                .join(Lead, Lead.id == Conversation.lead_id)
                .where(
                    Conversation.id == conversation_id,
                    Conversation.broker_id == broker_id,
                    Lead.broker_id == broker_id,
                )
            )
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        conversation, lead = row
        role = role_from_claims(current_user)
        if role == UserRole.AGENT.value and lead.assigned_to != user_id_from_claims(current_user):
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        if role == UserRole.SUPERADMIN.value and not allow_superadmin_send:
            raise HTTPException(
                status_code=403,
                detail="El superadministrador solo puede consultar; usa impersonación para enviar",
            )
        return conversation, lead

    @staticmethod
    def _base_projection(*, user_id: int):
        assigned_agent = aliased(User)
        last_message = (
            select(ChatMessage.message_text)
            .where(ChatMessage.conversation_id == Conversation.id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        last_direction = (
            select(ChatMessage.direction)
            .where(ChatMessage.conversation_id == Conversation.id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        last_at = func.coalesce(Conversation.last_message_at, Conversation.started_at)
        read_message_id = (
            select(ConversationReadState.last_read_message_id)
            .where(
                ConversationReadState.conversation_id == Conversation.id,
                ConversationReadState.user_id == user_id,
            )
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        unread_count = (
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.conversation_id == Conversation.id,
                ChatMessage.direction == MessageDirection.INBOUND,
                ChatMessage.id > func.coalesce(read_message_id, 0),
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        query = (
            select(
                Conversation,
                Lead,
                MetaAsset,
                assigned_agent.name.label("assigned_agent_name"),
                last_message.label("last_message"),
                last_direction.label("last_direction"),
                last_at.label("sort_at"),
                unread_count.label("unread_count"),
            )
            .join(Lead, Lead.id == Conversation.lead_id)
            .outerjoin(MetaAsset, MetaAsset.id == Conversation.meta_asset_id)
            .outerjoin(assigned_agent, assigned_agent.id == Lead.assigned_to)
        )
        return query, last_at

    @staticmethod
    def row_to_item(row) -> dict[str, Any]:
        conversation, lead, asset = row[0], row[1], row[2]
        lead_status = lead.status.value if hasattr(lead.status, "value") else lead.status
        direction = row.last_direction
        if hasattr(direction, "value"):
            direction = direction.value
        asset_payload = None
        if asset:
            asset_payload = {
                "id": asset.id,
                "type": asset.asset_type,
                "channel": asset.channel,
                "name": asset.display_name,
                "owner_type": asset.owner_type,
                "owner_user_id": asset.owner_user_id,
                "assigned_user_id": asset.assigned_user_id,
                "status": asset.status,
                "approval_status": asset.approval_status,
                "ai_mode": asset.ai_mode,
            }
        return {
            "id": conversation.id,
            "channel": conversation.channel,
            "status": conversation.status,
            "last_message": row.last_message,
            "last_message_at": row.sort_at,
            "last_message_direction": direction,
            "unread_count": int(row.unread_count or 0),
            "messaging_window_expires_at": conversation.messaging_window_expires_at,
            "assignment_conflict": bool(conversation.assignment_conflict),
            "human_mode": bool(conversation.human_mode),
            "message_count": int(conversation.message_count or 0),
            "asset": asset_payload,
            "lead": {
                "id": lead.id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "pipeline_stage": lead.pipeline_stage,
                "status": lead_status,
                "assigned_to": lead.assigned_to,
                "assigned_agent_name": row.assigned_agent_name,
            },
        }

    @staticmethod
    async def list_conversations(
        db: AsyncSession,
        *,
        current_user: dict,
        limit: int,
        cursor: Optional[str],
        channel: Optional[str],
        asset_id: Optional[int],
        assigned_user_id: Optional[int],
        pipeline_stage: Optional[str],
        project_id: Optional[int],
        status: Optional[str],
        search: Optional[str],
        from_at: Optional[datetime],
        to_at: Optional[datetime],
        conflict_only: bool,
    ) -> dict[str, Any]:
        broker_id = broker_id_from_claims(current_user)
        uid = user_id_from_claims(current_user)
        query, sort_at = MetaInboxService._base_projection(user_id=uid)
        query = query.where(
            Conversation.broker_id == broker_id,
            Lead.broker_id == broker_id,
            Conversation.meta_asset_id.isnot(None),
        )
        query = MetaInboxService._visibility(query, current_user)
        if channel:
            query = query.where(Conversation.channel == channel)
        if asset_id is not None:
            query = query.where(Conversation.meta_asset_id == asset_id)
        if assigned_user_id is not None:
            query = query.where(Lead.assigned_to == assigned_user_id)
        if pipeline_stage:
            query = query.where(Lead.pipeline_stage == pipeline_stage)
        if project_id is not None:
            query = query.where(exists(
                select(MetaLeadAttribution.id).where(
                    MetaLeadAttribution.broker_id == broker_id,
                    MetaLeadAttribution.lead_id == Lead.id,
                    MetaLeadAttribution.project_id == project_id,
                )
            ))
        if status:
            query = query.where(Conversation.status == status)
        if conflict_only:
            query = query.where(Conversation.assignment_conflict.is_(True))
        if search:
            term = f"%{search.strip()}%"
            query = query.where(or_(Lead.name.ilike(term), Lead.phone.ilike(term), Lead.email.ilike(term)))
        if from_at:
            query = query.where(sort_at >= from_at)
        if to_at:
            query = query.where(sort_at <= to_at)
        if cursor:
            cursor_at, cursor_id = _decode_cursor(cursor)
            query = query.where(
                or_(
                    sort_at < cursor_at,
                    and_(sort_at == cursor_at, Conversation.id < cursor_id),
                )
            )
        rows = list((await db.execute(
            query.order_by(desc(sort_at), Conversation.id.desc()).limit(limit + 1)
        )).all())
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [MetaInboxService.row_to_item(row) for row in page_rows]
        next_cursor = None
        if has_more and page_rows:
            next_cursor = _encode_cursor(page_rows[-1].sort_at, page_rows[-1][0].id)
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    @staticmethod
    async def item_for_conversation(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
    ) -> dict[str, Any]:
        await MetaInboxService.assert_access(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        uid = user_id_from_claims(current_user)
        query, _ = MetaInboxService._base_projection(user_id=uid)
        query = MetaInboxService._visibility(query, current_user).where(
            Conversation.id == conversation_id,
            Conversation.broker_id == broker_id_from_claims(current_user),
        )
        row = (await db.execute(query)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        return MetaInboxService.row_to_item(row)

    @staticmethod
    async def messages(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
        limit: int,
        before_id: Optional[int],
    ) -> dict[str, Any]:
        await MetaInboxService.assert_access(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        query = select(ChatMessage).where(
            ChatMessage.broker_id == broker_id_from_claims(current_user),
            ChatMessage.conversation_id == conversation_id,
        )
        if before_id is not None:
            query = query.where(ChatMessage.id < before_id)
        rows = list((await db.scalars(
            query.order_by(ChatMessage.id.desc()).limit(limit + 1)
        )).all())
        has_more = len(rows) > limit
        selected = rows[:limit]
        selected.reverse()
        items = []
        for message in selected:
            items.append({
                "id": message.id,
                "provider": message.provider.value if hasattr(message.provider, "value") else str(message.provider),
                "message_text": message.message_text,
                "direction": message.direction.value if hasattr(message.direction, "value") else str(message.direction),
                "status": message.status.value if hasattr(message.status, "value") else str(message.status),
                "message_type": message.message_type,
                "generation_mode": message.generation_mode,
                "channel_message_id": message.channel_message_id,
                "reply_to_external_id": message.reply_to_external_id,
                "sent_by_user_id": message.sent_by_user_id,
                "attachments": message.attachments,
                "remote_error_code": message.remote_error_code,
                "remote_error_subcode": message.remote_error_subcode,
                "created_at": message.created_at,
            })
        return {
            "items": items,
            "next_before_id": selected[0].id if has_more and selected else None,
            "has_more": has_more,
        }

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        *,
        conversation_id: int,
        current_user: dict,
    ) -> Optional[int]:
        await MetaInboxService.assert_access(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        )
        broker_id = broker_id_from_claims(current_user)
        uid = user_id_from_claims(current_user)
        last_message_id = await db.scalar(
            select(func.max(ChatMessage.id)).where(
                ChatMessage.broker_id == broker_id,
                ChatMessage.conversation_id == conversation_id,
            )
        )
        state = await db.scalar(
            select(ConversationReadState).where(
                ConversationReadState.conversation_id == conversation_id,
                ConversationReadState.user_id == uid,
            )
        )
        if not state:
            state = ConversationReadState(
                broker_id=broker_id,
                conversation_id=conversation_id,
                user_id=uid,
            )
            db.add(state)
        state.last_read_message_id = last_message_id
        state.read_at = datetime.now(timezone.utc)
        await db.commit()
        return last_message_id


class MetaAssignmentConflictService:
    @staticmethod
    async def list_open(db: AsyncSession, current_user: dict) -> list[MetaAssignmentConflict]:
        if role_from_claims(current_user) not in {UserRole.ADMIN.value, UserRole.SUPERADMIN.value}:
            raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
        result = await db.scalars(
            select(MetaAssignmentConflict).where(
                MetaAssignmentConflict.broker_id == broker_id_from_claims(current_user),
                MetaAssignmentConflict.status == "open",
            ).order_by(MetaAssignmentConflict.created_at.desc())
        )
        return list(result.all())

    @staticmethod
    async def resolve(
        db: AsyncSession,
        *,
        conflict_id: int,
        resolution: str,
        assigned_user_id: Optional[int],
        current_user: dict,
    ) -> MetaAssignmentConflict:
        if role_from_claims(current_user) != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Jefatura debe resolver el conflicto")
        broker_id = broker_id_from_claims(current_user)
        conflict = await db.scalar(
            select(MetaAssignmentConflict).where(
                MetaAssignmentConflict.id == conflict_id,
                MetaAssignmentConflict.broker_id == broker_id,
                MetaAssignmentConflict.status == "open",
            )
        )
        if not conflict:
            raise HTTPException(status_code=404, detail="Conflicto no encontrado")

        target_user_id = None
        if resolution == "transfer_to_asset_owner":
            target_user_id = conflict.asset_owner_id
            if target_user_id is None:
                raise HTTPException(status_code=422, detail="El activo no tiene ejecutivo responsable")
        elif resolution == "assign_user":
            if assigned_user_id is None:
                raise HTTPException(status_code=422, detail="Selecciona un ejecutivo")
            target_user_id = assigned_user_id
        if target_user_id is not None:
            await LeadAssignmentService.assign(
                db,
                lead_id=conflict.lead_id,
                agent_id=target_user_id,
                current_user=current_user,
            )

        conflict = await db.scalar(
            select(MetaAssignmentConflict).where(MetaAssignmentConflict.id == conflict_id)
        )
        conflict.status = "dismissed" if resolution == "dismiss" else "resolved"
        conflict.resolution = resolution
        conflict.resolved_by_user_id = user_id_from_claims(current_user)
        conflict.resolved_at = datetime.now(timezone.utc)
        conversations = list((await db.scalars(
            select(Conversation).where(
                Conversation.broker_id == broker_id,
                Conversation.lead_id == conflict.lead_id,
                Conversation.meta_asset_id == conflict.asset_id,
            )
        )).all())
        for conversation in conversations:
            conversation.assignment_conflict = False
        db.add(AuditLog(
            user_id=user_id_from_claims(current_user),
            broker_id=broker_id,
            action="meta_assignment_conflict_resolved",
            resource_type="meta_assignment_conflict",
            resource_id=conflict.id,
            changes={
                "resolution": resolution,
                "assigned_user_id": target_user_id,
                "lead_id": conflict.lead_id,
                "asset_id": conflict.asset_id,
            },
        ))
        await db.commit()
        await db.refresh(conflict)
        await ws_manager.broadcast(broker_id, "meta_assignment_conflict_resolved", {
            "conflict_id": conflict.id,
            "lead_id": conflict.lead_id,
            "asset_id": conflict.asset_id,
            "resolution": resolution,
        })
        return conflict
