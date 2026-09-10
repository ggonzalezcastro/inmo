"""Read-only audit for retiring legacy WhatsApp credential storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker_chat_config import BrokerChatConfig
from app.models.meta import MetaAsset, MetaCredential


LEGACY_SECRET_FIELDS = frozenset(
    {"access_token", "verify_token", "app_secret", "webhook_secret"}
)
LEGACY_ENVIRONMENT_VARIABLES = (
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_WEBHOOK_SECRET",
)
SUPPORTED_CREDENTIAL_PREFIX = "meta:v1:"


@dataclass(frozen=True)
class LegacySecretAuditReport:
    """Aggregate-only report; it never includes tenants, asset IDs or values."""

    broker_configs_scanned: int
    whatsapp_configs: int
    legacy_plaintext_secret_configs: int
    legacy_plaintext_secret_fields: int
    legacy_access_token_configs: int
    migrated_access_token_configs: int
    migration_gaps: int
    active_meta_credentials: int
    invalid_active_meta_credentials: int
    legacy_environment_variables_present: int
    fallback_enabled: bool

    def as_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def summarize_legacy_secret_state(
    *,
    configs: Iterable[BrokerChatConfig],
    assets: Iterable[MetaAsset],
    credentials: Iterable[MetaCredential],
    legacy_environment: Mapping[str, bool],
    fallback_enabled: bool,
) -> LegacySecretAuditReport:
    """Summarize migration and retirement readiness without exposing record data."""
    config_rows = list(configs)
    asset_rows = list(assets)
    credential_rows = list(credentials)

    active_credentials = [row for row in credential_rows if row.status == "active"]
    valid_connection_keys = {
        (row.broker_id, row.connection_id)
        for row in active_credentials
        if isinstance(row.encrypted_token, str)
        and row.encrypted_token.startswith(SUPPORTED_CREDENTIAL_PREFIX)
    }
    valid_asset_keys = {
        (row.broker_id, row.id)
        for row in active_credentials
        if row.asset_id is not None
        and isinstance(row.encrypted_token, str)
        and row.encrypted_token.startswith(SUPPORTED_CREDENTIAL_PREFIX)
    }
    whatsapp_assets = {
        (row.broker_id, str(row.external_id)): row
        for row in asset_rows
        if row.asset_type == "whatsapp_phone"
    }

    whatsapp_configs = 0
    plaintext_configs = 0
    plaintext_fields = 0
    access_token_configs = 0
    migrated_configs = 0

    for config in config_rows:
        provider_configs = config.provider_configs
        if not isinstance(provider_configs, dict):
            continue
        raw_whatsapp = provider_configs.get("whatsapp")
        if not isinstance(raw_whatsapp, dict):
            continue
        whatsapp_configs += 1
        present_secret_fields = {
            key for key in LEGACY_SECRET_FIELDS if raw_whatsapp.get(key)
        }
        if present_secret_fields:
            plaintext_configs += 1
            plaintext_fields += len(present_secret_fields)

        if not raw_whatsapp.get("access_token"):
            continue
        access_token_configs += 1
        phone_id = str(raw_whatsapp.get("phone_number_id") or "").strip()
        asset = whatsapp_assets.get((config.broker_id, phone_id))
        if asset is None:
            continue
        connection_key = (config.broker_id, asset.connection_id)
        asset_key = (config.broker_id, asset.id)
        if connection_key in valid_connection_keys or asset_key in valid_asset_keys:
            migrated_configs += 1

    invalid_credentials = sum(
        not isinstance(row.encrypted_token, str)
        or not row.encrypted_token.startswith(SUPPORTED_CREDENTIAL_PREFIX)
        for row in active_credentials
    )
    environment_present = sum(
        bool(legacy_environment.get(key)) for key in LEGACY_ENVIRONMENT_VARIABLES
    )

    return LegacySecretAuditReport(
        broker_configs_scanned=len(config_rows),
        whatsapp_configs=whatsapp_configs,
        legacy_plaintext_secret_configs=plaintext_configs,
        legacy_plaintext_secret_fields=plaintext_fields,
        legacy_access_token_configs=access_token_configs,
        migrated_access_token_configs=migrated_configs,
        migration_gaps=access_token_configs - migrated_configs,
        active_meta_credentials=len(active_credentials),
        invalid_active_meta_credentials=invalid_credentials,
        legacy_environment_variables_present=environment_present,
        fallback_enabled=fallback_enabled,
    )


async def audit_legacy_secret_state(
    db: AsyncSession,
    *,
    legacy_environment: Mapping[str, bool],
    fallback_enabled: bool,
) -> LegacySecretAuditReport:
    """Load the minimum required rows and return an aggregate-only audit."""
    configs = list((await db.scalars(select(BrokerChatConfig))).all())
    assets = list((await db.scalars(select(MetaAsset))).all())
    credentials = list((await db.scalars(select(MetaCredential))).all())
    return summarize_legacy_secret_state(
        configs=configs,
        assets=assets,
        credentials=credentials,
        legacy_environment=legacy_environment,
        fallback_enabled=fallback_enabled,
    )


def migration_readiness_errors(report: LegacySecretAuditReport) -> list[str]:
    errors: list[str] = []
    if report.migration_gaps:
        errors.append(
            f"{report.migration_gaps} legacy access-token configuration(s) lack an encrypted asset mapping"
        )
    if report.invalid_active_meta_credentials:
        errors.append(
            f"{report.invalid_active_meta_credentials} active Meta credential(s) use an unsupported format"
        )
    return errors


def retirement_errors(report: LegacySecretAuditReport) -> list[str]:
    errors = migration_readiness_errors(report)
    if report.legacy_plaintext_secret_fields:
        errors.append(
            f"{report.legacy_plaintext_secret_fields} legacy plaintext secret field(s) remain"
        )
    if report.legacy_environment_variables_present:
        errors.append(
            f"{report.legacy_environment_variables_present} legacy environment variable(s) remain"
        )
    if report.fallback_enabled:
        errors.append("legacy WhatsApp fallback is still enabled")
    return errors
