"""Resolve a Meta asset and its encrypted credential without crossing tenants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.meta_encryption import decrypt_meta_secret
from app.models.conversation import Conversation
from app.models.meta import MetaAsset, MetaConnection, MetaCredential


class MetaAssetResolutionError(LookupError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedMetaAsset:
    broker_id: int
    connection_id: int
    asset_id: int
    asset_type: str
    channel: Optional[str]
    external_id: str
    access_token: str
    owner_user_id: Optional[int]
    assigned_user_id: Optional[int]
    capabilities: tuple[str, ...]
    ai_mode: str


class MetaAssetResolver:
    @staticmethod
    async def by_external_id(
        db: AsyncSession,
        *,
        asset_type: str,
        external_id: str,
        broker_id: Optional[int] = None,
        require_capability: Optional[str] = None,
    ) -> ResolvedMetaAsset:
        filters = [
            MetaAsset.asset_type == asset_type,
            MetaAsset.external_id == str(external_id),
            MetaAsset.status == "active",
            MetaAsset.approval_status == "approved",
            MetaConnection.status == "active",
        ]
        if broker_id is not None:
            filters.append(MetaAsset.broker_id == int(broker_id))

        row = (
            await db.execute(
                select(MetaAsset, MetaConnection)
                .join(MetaConnection, MetaConnection.id == MetaAsset.connection_id)
                .where(*filters)
            )
        ).first()
        if not row:
            raise MetaAssetResolutionError("ASSET_NOT_FOUND", "Activo Meta no disponible")
        asset, connection = row
        capabilities = tuple(asset.capabilities or [])
        if require_capability and require_capability not in capabilities:
            raise MetaAssetResolutionError(
                "CAPABILITY_NOT_ALLOWED",
                f"El activo no permite {require_capability}",
            )

        credential = await db.scalar(
            select(MetaCredential)
            .where(
                MetaCredential.broker_id == asset.broker_id,
                MetaCredential.connection_id == connection.id,
                MetaCredential.status == "active",
                or_(
                    MetaCredential.asset_id == asset.id,
                    MetaCredential.asset_id.is_(None),
                ),
            )
            .order_by(MetaCredential.asset_id.desc().nullslast(), MetaCredential.id.desc())
            .limit(1)
        )
        if not credential:
            raise MetaAssetResolutionError("CREDENTIAL_NOT_FOUND", "Credencial Meta no disponible")

        return ResolvedMetaAsset(
            broker_id=asset.broker_id,
            connection_id=connection.id,
            asset_id=asset.id,
            asset_type=asset.asset_type,
            channel=asset.channel,
            external_id=asset.external_id,
            access_token=decrypt_meta_secret(credential.encrypted_token),
            owner_user_id=asset.owner_user_id,
            assigned_user_id=asset.assigned_user_id,
            capabilities=capabilities,
            ai_mode=asset.ai_mode,
        )

    @staticmethod
    async def for_conversation(
        db: AsyncSession,
        *,
        broker_id: int,
        conversation_id: int,
        require_capability: str = "messaging",
    ) -> ResolvedMetaAsset:
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.broker_id == broker_id,
            )
        )
        if not conversation or not conversation.meta_asset_id:
            raise MetaAssetResolutionError(
                "CONVERSATION_ASSET_MISSING",
                "La conversación no tiene un activo Meta asociado",
            )
        asset = await db.scalar(
            select(MetaAsset).where(
                MetaAsset.id == conversation.meta_asset_id,
                MetaAsset.broker_id == broker_id,
            )
        )
        if not asset:
            raise MetaAssetResolutionError("ASSET_NOT_FOUND", "Activo Meta no disponible")
        return await MetaAssetResolver.by_external_id(
            db,
            asset_type=asset.asset_type,
            external_id=asset.external_id,
            broker_id=broker_id,
            require_capability=require_capability,
        )
