"""Connection validation, expiry warning, and lightweight asset synchronization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.meta_encryption import decrypt_meta_secret
from app.core.websocket_manager import ws_manager
from app.models.audit_log import AuditLog
from app.models.meta import MetaAsset, MetaConnection, MetaCredential, MetaMessageTemplate
from app.services.meta.client import MetaGraphClient, MetaGraphError


def _uid(current_user: Optional[dict]) -> Optional[int]:
    if not current_user:
        return None
    raw = current_user.get("user_id") or current_user.get("id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


class MetaConnectionHealthService:
    @staticmethod
    async def _connection_and_token(
        db: AsyncSession,
        *,
        connection_id: int,
        broker_id: Optional[int] = None,
    ) -> tuple[MetaConnection, MetaCredential, str]:
        filters = [MetaConnection.id == connection_id]
        if broker_id is not None:
            filters.append(MetaConnection.broker_id == broker_id)
        connection = await db.scalar(select(MetaConnection).where(*filters))
        if not connection:
            raise HTTPException(status_code=404, detail="Conexión Meta no encontrada")
        credential = await db.scalar(
            select(MetaCredential)
            .where(
                MetaCredential.connection_id == connection.id,
                MetaCredential.asset_id.is_(None),
                MetaCredential.status == "active",
            )
            .order_by(MetaCredential.id.desc())
            .limit(1)
        )
        if not credential:
            raise HTTPException(status_code=409, detail="La conexión no tiene credencial activa")
        return connection, credential, decrypt_meta_secret(credential.encrypted_token)

    @staticmethod
    async def revalidate(
        db: AsyncSession,
        *,
        connection_id: int,
        broker_id: Optional[int] = None,
        current_user: Optional[dict] = None,
    ) -> MetaConnection:
        connection, credential, token = await MetaConnectionHealthService._connection_and_token(
            db,
            connection_id=connection_id,
            broker_id=broker_id,
        )
        if current_user:
            role = str(current_user.get("role") or "").upper()
            uid = _uid(current_user)
            if role == "SUPERADMIN":
                raise HTTPException(
                    status_code=403,
                    detail="El superadministrador solo puede consultar; usa impersonación para administrar",
                )
            if role == "AGENT" and connection.owner_user_id != uid:
                raise HTTPException(status_code=403, detail="No puedes validar esta conexión")
            if role not in {"ADMIN", "AGENT"}:
                raise HTTPException(status_code=403, detail="Permiso insuficiente")
        previous = connection.status
        now = datetime.now(timezone.utc)
        try:
            if connection.auth_mode == "instagram_login":
                graph = MetaGraphClient(
                    access_token=token,
                    app_secret=settings.META_INSTAGRAM_APP_SECRET,
                    base_url="https://graph.instagram.com",
                )
                await graph.get("me", params={"fields": "id,username,account_type"})
                connection.status = "active"
                connection.revoked_at = None
                connection.last_error_code = None
                connection.last_error_detail = None
            else:
                app_access_token = f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
                graph = MetaGraphClient(
                    access_token=app_access_token,
                    app_secret="",
                )
                response = await graph.get("debug_token", params={"input_token": token})
                data = response.get("data") or {}
                if not data.get("is_valid"):
                    connection.status = "revoked"
                    connection.revoked_at = now
                    credential.status = "revoked"
                    connection.last_error_code = "TOKEN_INVALID"
                    connection.last_error_detail = "Meta informó que la autorización ya no es válida"
                elif data.get("app_id") and str(data["app_id"]) != str(settings.META_APP_ID):
                    connection.status = "error"
                    connection.last_error_code = "WRONG_APP"
                    connection.last_error_detail = "La credencial pertenece a otra aplicación Meta"
                else:
                    connection.status = "active"
                    connection.revoked_at = None
                    connection.last_error_code = None
                    connection.last_error_detail = None
                    scopes = sorted(set(data.get("scopes") or connection.scopes or []))
                    connection.scopes = scopes
                    credential.scopes = scopes
                    expires_timestamp = data.get("expires_at")
                    if expires_timestamp:
                        expires_at = datetime.fromtimestamp(int(expires_timestamp), tz=timezone.utc)
                        connection.expires_at = expires_at
                        credential.expires_at = expires_at
            connection.last_validated_at = now
            credential.last_validated_at = now
        except MetaGraphError as exc:
            connection.status = "degraded" if exc.is_transient else "revoked"
            connection.last_error_code = exc.category
            connection.last_error_detail = "Meta no pudo validar la autorización"
            if connection.status == "revoked":
                connection.revoked_at = now
                credential.status = "revoked"

        metadata = dict(connection.connection_metadata or {})
        exp = connection.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        should_warn = bool(exp and exp <= now + timedelta(days=7))
        warned_at = metadata.get("expiry_notified_at")
        if should_warn and not warned_at:
            metadata["expiry_notified_at"] = now.isoformat()
            await ws_manager.broadcast(connection.broker_id, "meta_connection_expiring", {
                "connection_id": connection.id,
                "owner_user_id": connection.owner_user_id,
                "expires_at": exp.isoformat() if exp else None,
            })
        elif not should_warn:
            metadata.pop("expiry_notified_at", None)
        connection.connection_metadata = metadata

        if previous != connection.status:
            db.add(AuditLog(
                user_id=_uid(current_user),
                broker_id=connection.broker_id,
                action="meta_connection_health_changed",
                resource_type="meta_connection",
                resource_id=connection.id,
                changes={"before": previous, "after": connection.status},
            ))
        await db.commit()
        await db.refresh(connection)
        if previous != connection.status:
            await ws_manager.broadcast(connection.broker_id, "meta_connection_health_changed", {
                "connection_id": connection.id,
                "status": connection.status,
                "error_code": connection.last_error_code,
            })
        return connection

    @staticmethod
    async def sync_assets(
        db: AsyncSession,
        *,
        connection_id: int,
        broker_id: Optional[int] = None,
        current_user: Optional[dict] = None,
    ) -> int:
        connection, _, token = await MetaConnectionHealthService._connection_and_token(
            db,
            connection_id=connection_id,
            broker_id=broker_id,
        )
        graph = MetaGraphClient(
            access_token=token,
            app_secret=(
                settings.META_INSTAGRAM_APP_SECRET
                if connection.auth_mode == "instagram_login"
                else settings.META_APP_SECRET
            ),
            base_url=(
                "https://graph.instagram.com"
                if connection.auth_mode == "instagram_login"
                else "https://graph.facebook.com"
            ),
        )
        assets = list((await db.scalars(
            select(MetaAsset).where(
                MetaAsset.connection_id == connection.id,
                MetaAsset.broker_id == connection.broker_id,
            )
        )).all())
        synced = 0
        now = datetime.now(timezone.utc)
        field_map = {
            "waba": "id,name",
            "whatsapp_phone": "id,display_phone_number,verified_name,quality_rating",
            "facebook_page": "id,name",
            "instagram_account": "id,username,account_type",
            "ad_account": "id,name,account_status,currency,timezone_name",
            "pixel": "id,name",
        }
        for asset in assets:
            fields = field_map.get(asset.asset_type)
            if not fields:
                continue
            try:
                data = await graph.get(asset.external_id, params={"fields": fields})
                metadata = dict(asset.asset_metadata or {})
                metadata.update({key: value for key, value in data.items() if key != "access_token"})
                asset.asset_metadata = metadata
                asset.display_name = (
                    data.get("verified_name")
                    or data.get("username")
                    or data.get("name")
                    or asset.display_name
                )
                asset.last_synced_at = now
                asset.last_error_code = None
                asset.last_error_detail = None
                synced += 1
                if asset.asset_type == "waba":
                    async for template_data in graph.iterate(
                        f"{asset.external_id}/message_templates",
                        params={
                            "fields": "id,name,language,category,status,components",
                            "limit": 100,
                        },
                    ):
                        name = str(template_data.get("name") or "")
                        language = str(template_data.get("language") or "")
                        if not name or not language:
                            continue
                        template = await db.scalar(
                            select(MetaMessageTemplate).where(
                                MetaMessageTemplate.broker_id == connection.broker_id,
                                MetaMessageTemplate.waba_external_id == asset.external_id,
                                MetaMessageTemplate.name == name,
                                MetaMessageTemplate.language == language,
                            )
                        )
                        if not template:
                            template = MetaMessageTemplate(
                                broker_id=connection.broker_id,
                                connection_id=connection.id,
                                waba_external_id=asset.external_id,
                                external_id=str(template_data.get("id") or f"{name}:{language}"),
                                name=name,
                                language=language,
                                status=str(template_data.get("status") or "PENDING").upper(),
                            )
                            db.add(template)
                        template.connection_id = connection.id
                        template.external_id = str(
                            template_data.get("id") or template.external_id
                        )
                        template.category = template_data.get("category")
                        template.status = str(
                            template_data.get("status") or "PENDING"
                        ).upper()
                        template.components = template_data.get("components") or []
                        template.last_synced_at = now
            except MetaGraphError as exc:
                asset.last_error_code = exc.category
                asset.last_error_detail = "No se pudo sincronizar el activo"
        db.add(AuditLog(
            user_id=_uid(current_user),
            broker_id=connection.broker_id,
            action="meta_assets_synchronized",
            resource_type="meta_connection",
            resource_id=connection.id,
            changes={"asset_count": synced, "total": len(assets)},
        ))
        await db.commit()
        await ws_manager.broadcast(connection.broker_id, "meta_assets_synchronized", {
            "connection_id": connection.id,
            "asset_count": synced,
        })
        return synced

    @staticmethod
    async def connection_ids_for_maintenance(db: AsyncSession) -> list[int]:
        result = await db.scalars(
            select(MetaConnection.id).where(
                or_(
                    MetaConnection.status.in_(["active", "degraded"]),
                    MetaConnection.expires_at < datetime.now(timezone.utc) + timedelta(days=7),
                )
            )
        )
        return list(result.all())


class MetaMessageTemplateService:
    @staticmethod
    async def list_for_phone(
        db: AsyncSession,
        *,
        broker_id: int,
        phone_asset_id: int,
        approved_only: bool = True,
    ) -> list[MetaMessageTemplate]:
        phone = await db.scalar(
            select(MetaAsset).where(
                MetaAsset.id == phone_asset_id,
                MetaAsset.broker_id == broker_id,
                MetaAsset.asset_type == "whatsapp_phone",
            )
        )
        if not phone:
            raise HTTPException(status_code=404, detail="Número WhatsApp no encontrado")
        query = select(MetaMessageTemplate).where(
            MetaMessageTemplate.broker_id == broker_id,
            MetaMessageTemplate.connection_id == phone.connection_id,
            MetaMessageTemplate.waba_external_id == phone.parent_external_id,
        )
        if approved_only:
            query = query.where(MetaMessageTemplate.status == "APPROVED")
        result = await db.scalars(
            query.order_by(MetaMessageTemplate.name.asc(), MetaMessageTemplate.language.asc())
        )
        return list(result.all())
