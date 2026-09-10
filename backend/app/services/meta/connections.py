"""Connection and asset lifecycle with tenant and role enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.meta_encryption import encrypt_meta_secret
from app.models.audit_log import AuditLog
from app.models.meta import MetaAsset, MetaConnection, MetaCredential
from app.models.user import User, UserRole


def _user_id(current_user: dict) -> Optional[int]:
    raw = current_user.get("user_id") or current_user.get("id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _broker_id(current_user: dict) -> int:
    raw = current_user.get("broker_id")
    if raw is None:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")
    return int(raw)


def _role(current_user: dict) -> str:
    return str(current_user.get("role") or "").upper()


class MetaConnectionService:
    @staticmethod
    async def create_or_update(
        db: AsyncSession,
        *,
        broker_id: int,
        owner_type: str,
        owner_user_id: Optional[int],
        connected_by_user_id: Optional[int],
        auth_mode: str,
        external_principal_id: str,
        access_token: str,
        display_name: Optional[str] = None,
        scopes: Optional[Iterable[str]] = None,
        expires_at: Optional[datetime] = None,
        connection_metadata: Optional[dict] = None,
    ) -> MetaConnection:
        if owner_type not in {"broker", "executive"}:
            raise ValueError("owner_type inválido")
        if owner_type == "broker":
            owner_user_id = None
        elif owner_user_id is None:
            raise ValueError("Una conexión de ejecutivo requiere owner_user_id")

        connection = await db.scalar(
            select(MetaConnection).where(
                MetaConnection.broker_id == broker_id,
                MetaConnection.auth_mode == auth_mode,
                MetaConnection.external_principal_id == str(external_principal_id),
            )
        )
        now = datetime.now(timezone.utc)
        if connection is None:
            connection = MetaConnection(
                broker_id=broker_id,
                owner_type=owner_type,
                owner_user_id=owner_user_id,
                connected_by_user_id=connected_by_user_id,
                auth_mode=auth_mode,
                external_principal_id=str(external_principal_id),
            )
            db.add(connection)
            await db.flush()
        connection.owner_type = owner_type
        connection.owner_user_id = owner_user_id
        connection.connected_by_user_id = connected_by_user_id
        connection.display_name = display_name
        connection.scopes = sorted(set(scopes or []))
        connection.status = "active"
        connection.expires_at = expires_at
        connection.last_validated_at = now
        connection.revoked_at = None
        connection.disconnected_at = None
        connection.last_error_code = None
        connection.last_error_detail = None
        connection.connection_metadata = connection_metadata or {}

        credential = await db.scalar(
            select(MetaCredential).where(
                MetaCredential.connection_id == connection.id,
                MetaCredential.subject_type == "connection",
                MetaCredential.subject_external_id == str(external_principal_id),
            )
        )
        if credential is None:
            credential = MetaCredential(
                broker_id=broker_id,
                connection_id=connection.id,
                subject_type="connection",
                subject_external_id=str(external_principal_id),
            )
            db.add(credential)
        credential.encrypted_token = encrypt_meta_secret(access_token)
        credential.scopes = connection.scopes
        credential.expires_at = expires_at
        credential.status = "active"
        credential.last_validated_at = now

        db.add(AuditLog(
            user_id=connected_by_user_id,
            broker_id=broker_id,
            action="meta_connection_upserted",
            resource_type="meta_connection",
            resource_id=connection.id,
            changes={
                "auth_mode": auth_mode,
                "owner_type": owner_type,
                "owner_user_id": owner_user_id,
                "scopes": connection.scopes,
            },
        ))
        await db.commit()
        await db.refresh(connection)
        return connection

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        current_user: dict,
    ) -> list[MetaConnection]:
        broker_id = _broker_id(current_user)
        query = select(MetaConnection).where(MetaConnection.broker_id == broker_id)
        if _role(current_user) == UserRole.AGENT.value:
            query = query.where(MetaConnection.owner_user_id == _user_id(current_user))
        elif _role(current_user) not in {UserRole.ADMIN.value, UserRole.SUPERADMIN.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        result = await db.scalars(query.order_by(MetaConnection.created_at.desc()))
        return list(result.all())

    @staticmethod
    async def disconnect(
        db: AsyncSession,
        *,
        connection_id: int,
        current_user: dict,
    ) -> MetaConnection:
        broker_id = _broker_id(current_user)
        connection = await db.scalar(
            select(MetaConnection).where(
                MetaConnection.id == connection_id,
                MetaConnection.broker_id == broker_id,
            )
        )
        if not connection:
            raise HTTPException(status_code=404, detail="Conexión Meta no encontrada")
        uid = _user_id(current_user)
        role = _role(current_user)
        if role == UserRole.SUPERADMIN.value:
            raise HTTPException(
                status_code=403,
                detail="El superadministrador solo puede consultar; usa impersonación para administrar",
            )
        if role == UserRole.AGENT.value and connection.owner_user_id != uid:
            raise HTTPException(status_code=403, detail="No puedes desconectar esta conexión")
        if role not in {UserRole.ADMIN.value, UserRole.AGENT.value}:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")

        now = datetime.now(timezone.utc)
        connection.status = "disconnected"
        connection.disconnected_at = now
        await db.execute(
            update(MetaAsset)
            .where(MetaAsset.connection_id == connection.id)
            .values(status="paused", is_default=False)
        )
        await db.execute(
            update(MetaCredential)
            .where(MetaCredential.connection_id == connection.id)
            .values(status="revoked")
        )
        db.add(AuditLog(
            user_id=uid,
            broker_id=broker_id,
            action="meta_connection_disconnected",
            resource_type="meta_connection",
            resource_id=connection.id,
            changes={"status": "disconnected"},
        ))
        await db.commit()
        await db.refresh(connection)
        return connection


class MetaAssetService:
    @staticmethod
    async def list_for_user(db: AsyncSession, current_user: dict) -> list[MetaAsset]:
        broker_id = _broker_id(current_user)
        query = select(MetaAsset).where(MetaAsset.broker_id == broker_id)
        if _role(current_user) == UserRole.AGENT.value:
            uid = _user_id(current_user)
            query = query.where(
                or_(MetaAsset.owner_user_id == uid, MetaAsset.assigned_user_id == uid)
            )
        result = await db.scalars(
            query.order_by(MetaAsset.channel.asc().nullslast(), MetaAsset.display_name.asc())
        )
        return list(result.all())

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        asset_id: int,
        current_user: dict,
        changes: dict,
    ) -> MetaAsset:
        if _role(current_user) != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
        broker_id = _broker_id(current_user)
        changes = dict(changes)
        asset = await db.scalar(
            select(MetaAsset).where(
                MetaAsset.id == asset_id,
                MetaAsset.broker_id == broker_id,
            ).with_for_update()
        )
        if not asset:
            raise HTTPException(status_code=404, detail="Activo Meta no encontrado")

        if "assigned_user_id" in changes and changes["assigned_user_id"] is not None:
            agent = await db.scalar(
                select(User).where(
                    User.id == changes["assigned_user_id"],
                    User.broker_id == broker_id,
                    User.role == UserRole.AGENT,
                    User.is_active.is_(True),
                )
            )
            if not agent:
                raise HTTPException(
                    status_code=422,
                    detail="El responsable debe ser un ejecutivo activo del mismo broker",
                )

        capabilities = changes.get("capabilities")
        if asset.owner_type == "executive" and capabilities is not None:
            forbidden = {"ads", "leadgen"}.intersection(capabilities)
            if forbidden:
                raise HTTPException(
                    status_code=422,
                    detail="Los activos de ejecutivos solo pueden usar mensajería",
                )

        if changes.get("is_default") is True:
            if asset.asset_type == "pixel":
                next_owner = changes.get("owner_type", asset.owner_type)
                next_approval = changes.get("approval_status", asset.approval_status)
                next_status = changes.get("status", asset.status)
                if (
                    next_owner != "broker"
                    or next_approval != "approved"
                    or next_status != "active"
                    or "conversions" not in (asset.capabilities or [])
                ):
                    raise HTTPException(
                        status_code=422,
                        detail="Solo un dataset corporativo activo y aprobado puede recibir conversiones",
                    )
                default_scope = (
                    MetaAsset.broker_id == broker_id,
                    MetaAsset.asset_type == "pixel",
                    MetaAsset.owner_type == "broker",
                    MetaAsset.id != asset.id,
                )
            else:
                if not asset.channel:
                    raise HTTPException(status_code=422, detail="El activo no pertenece a un canal")
                default_scope = (
                    MetaAsset.broker_id == broker_id,
                    MetaAsset.channel == asset.channel,
                    MetaAsset.id != asset.id,
                )
            await db.execute(update(MetaAsset).where(*default_scope).values(is_default=False))

        if asset.asset_type == "pixel" and asset.is_default:
            next_approval = changes.get("approval_status", asset.approval_status)
            next_status = changes.get("status", asset.status)
            next_capabilities = changes.get("capabilities", asset.capabilities or [])
            if (
                next_approval != "approved"
                or next_status != "active"
                or "conversions" not in next_capabilities
            ):
                changes["is_default"] = False
        before = {
            key: getattr(asset, key)
            for key in changes
            if hasattr(asset, key)
        }
        for key, value in changes.items():
            if hasattr(asset, key):
                setattr(asset, key, value)

        db.add(AuditLog(
            user_id=_user_id(current_user),
            broker_id=broker_id,
            action="meta_asset_updated",
            resource_type="meta_asset",
            resource_id=asset.id,
            changes={"before": before, "after": changes},
        ))
        await db.commit()
        await db.refresh(asset)
        return asset
