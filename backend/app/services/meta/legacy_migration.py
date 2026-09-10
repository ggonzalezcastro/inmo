"""Idempotent conversion of legacy per-broker WhatsApp configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.meta_encryption import encrypt_meta_secret
from app.models.broker_chat_config import BrokerChatConfig
from app.models.meta import MetaAsset, MetaConnection, MetaCredential


@dataclass
class LegacyWhatsAppMigrationItem:
    broker_id: int
    status: str
    phone_number_id: Optional[str] = None
    detail: Optional[str] = None


@dataclass
class LegacyWhatsAppMigrationReport:
    dry_run: bool
    scanned: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    conflicts: int = 0
    items: list[LegacyWhatsAppMigrationItem] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LegacyWhatsAppMigrationService:
    """Backfill legacy JSON credentials without deleting or mutating the source."""

    @staticmethod
    def _legacy_values(config: BrokerChatConfig) -> tuple[dict[str, Any], str, str, str]:
        values = dict((config.provider_configs or {}).get("whatsapp") or {})
        phone_id = str(values.get("phone_number_id") or "").strip()
        access_token = str(values.get("access_token") or "").strip()
        waba_id = str(
            values.get("waba_id")
            or values.get("business_account_id")
            or values.get("whatsapp_business_account_id")
            or f"legacy-broker-{config.broker_id}"
        ).strip()
        return values, phone_id, access_token, waba_id

    @staticmethod
    async def run(
        db: AsyncSession,
        *,
        dry_run: bool = True,
        broker_id: Optional[int] = None,
    ) -> LegacyWhatsAppMigrationReport:
        query = select(BrokerChatConfig).order_by(BrokerChatConfig.broker_id.asc())
        if broker_id is not None:
            query = query.where(BrokerChatConfig.broker_id == broker_id)
        configs = list((await db.scalars(query)).all())
        report = LegacyWhatsAppMigrationReport(dry_run=dry_run, scanned=len(configs))

        for config in configs:
            values, phone_id, access_token, waba_id = (
                LegacyWhatsAppMigrationService._legacy_values(config)
            )
            if not phone_id or not access_token:
                report.skipped += 1
                report.items.append(LegacyWhatsAppMigrationItem(
                    broker_id=config.broker_id,
                    status="skipped",
                    phone_number_id=phone_id or None,
                    detail="Falta phone_number_id o access_token",
                ))
                continue

            foreign_asset = await db.scalar(
                select(MetaAsset).where(
                    MetaAsset.asset_type == "whatsapp_phone",
                    MetaAsset.external_id == phone_id,
                    MetaAsset.broker_id != config.broker_id,
                )
            )
            if foreign_asset:
                report.conflicts += 1
                report.items.append(LegacyWhatsAppMigrationItem(
                    broker_id=config.broker_id,
                    status="conflict",
                    phone_number_id=phone_id,
                    detail="El phone_number_id ya pertenece a otro broker",
                ))
                continue

            existing_connection = await db.scalar(
                select(MetaConnection).where(
                    MetaConnection.broker_id == config.broker_id,
                    MetaConnection.auth_mode == "legacy_whatsapp",
                    MetaConnection.external_principal_id == waba_id,
                )
            )
            existing_asset = await db.scalar(
                select(MetaAsset).where(
                    MetaAsset.broker_id == config.broker_id,
                    MetaAsset.asset_type == "whatsapp_phone",
                    MetaAsset.external_id == phone_id,
                )
            )
            item_status = "updated" if existing_connection or existing_asset else "created"
            if dry_run:
                setattr(report, item_status, getattr(report, item_status) + 1)
                report.items.append(LegacyWhatsAppMigrationItem(
                    broker_id=config.broker_id,
                    status=f"would_{item_status}",
                    phone_number_id=phone_id,
                ))
                continue

            now = datetime.now(timezone.utc)
            connection = existing_connection
            if connection is None:
                connection = MetaConnection(
                    broker_id=config.broker_id,
                    owner_type="broker",
                    owner_user_id=None,
                    connected_by_user_id=None,
                    auth_mode="legacy_whatsapp",
                    external_principal_id=waba_id,
                )
                db.add(connection)
                await db.flush()
            connection.display_name = values.get("business_name") or "WhatsApp migrado"
            connection.scopes = ["whatsapp_business_messaging"]
            connection.status = "active"
            connection.last_validated_at = now
            connection.connection_metadata = {
                "migration_source": "broker_chat_configs",
                "legacy_config_id": config.id,
            }

            credential = await db.scalar(
                select(MetaCredential).where(
                    MetaCredential.connection_id == connection.id,
                    MetaCredential.subject_type == "connection",
                    MetaCredential.subject_external_id == waba_id,
                )
            )
            if credential is None:
                credential = MetaCredential(
                    broker_id=config.broker_id,
                    connection_id=connection.id,
                    subject_type="connection",
                    subject_external_id=waba_id,
                )
                db.add(credential)
            credential.encrypted_token = encrypt_meta_secret(access_token)
            credential.scopes = ["whatsapp_business_messaging"]
            credential.status = "active"
            credential.last_validated_at = now

            asset = existing_asset
            if asset is None:
                asset = MetaAsset(
                    broker_id=config.broker_id,
                    connection_id=connection.id,
                    asset_type="whatsapp_phone",
                    channel="whatsapp",
                    external_id=phone_id,
                    parent_external_id=waba_id,
                    owner_type="broker",
                )
                db.add(asset)
            asset.connection_id = connection.id
            asset.display_name = values.get("display_phone_number") or values.get("display_name") or phone_id
            asset.capabilities = ["messaging", "templates", "message_status"]
            asset.approval_status = "approved"
            asset.status = "active"
            asset.is_default = True
            # Preserve the legacy inbound behavior when the new routing flag is enabled.
            asset.ai_mode = "supervised_auto"
            asset.last_synced_at = now
            asset.asset_metadata = {
                "migration_source": "broker_chat_configs",
                "legacy_config_id": config.id,
            }

            setattr(report, item_status, getattr(report, item_status) + 1)
            report.items.append(LegacyWhatsAppMigrationItem(
                broker_id=config.broker_id,
                status=item_status,
                phone_number_id=phone_id,
            ))

        if dry_run:
            await db.rollback()
        else:
            await db.commit()
        return report
