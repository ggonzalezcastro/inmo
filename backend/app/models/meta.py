"""Multi-tenant Meta connections, assets, identities, and durable webhook inbox."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin


META_OWNER_TYPES = ("broker", "user")
META_CONNECTION_STATUSES = (
    "pending",
    "active",
    "degraded",
    "revoked",
    "disconnected",
    "error",
)
META_ASSET_TYPES = (
    "waba",
    "whatsapp_phone",
    "instagram_account",
    "facebook_page",
    "ad_account",
    "pixel",
    "lead_form",
)
META_ASSET_STATUSES = ("active", "paused", "disabled", "error")
META_APPROVAL_STATUSES = ("pending_approval", "approved", "rejected")
META_AI_MODES = ("suggestion", "supervised_auto", "human")
META_WEBHOOK_STATUSES = ("pending", "processing", "processed", "failed", "ignored")
META_CONFLICT_STATUSES = ("open", "resolved", "dismissed")


class MetaConnection(Base, IdMixin, TimestampMixin):
    """OAuth/business authorization root for one broker or user."""

    __tablename__ = "meta_connections"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_type = Column(String(20), nullable=False)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    connected_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    auth_mode = Column(String(40), nullable=False, index=True)
    external_principal_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    scopes = Column(JSONB, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="pending", index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(100), nullable=True)
    last_error_detail = Column(Text, nullable=True)
    connection_metadata = Column(JSONB, nullable=False, default=dict)

    broker = relationship("Broker", foreign_keys=[broker_id])
    owner_user = relationship("User", foreign_keys=[owner_user_id])
    connected_by_user = relationship("User", foreign_keys=[connected_by_user_id])
    assets = relationship(
        "MetaAsset",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    credentials = relationship(
        "MetaCredential",
        back_populates="connection",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "broker_id",
            "auth_mode",
            "external_principal_id",
            name="uq_meta_connection_principal",
        ),
        CheckConstraint(
            "owner_type IN ('broker', 'user')",
            name="ck_meta_connection_owner_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'degraded', 'revoked', 'disconnected', 'error')",
            name="ck_meta_connection_status",
        ),
        CheckConstraint(
            "(owner_type = 'broker' AND owner_user_id IS NULL) OR "
            "(owner_type = 'user' AND owner_user_id IS NOT NULL)",
            name="ck_meta_connection_owner_user",
        ),
        Index("idx_meta_connections_broker_status", "broker_id", "status"),
    )


class MetaAsset(Base, IdMixin, TimestampMixin):
    """A Meta business asset made available through a connection."""

    __tablename__ = "meta_assets"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey("meta_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_type = Column(String(40), nullable=False, index=True)
    channel = Column(String(30), nullable=True, index=True)
    external_id = Column(String(255), nullable=False)
    parent_external_id = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    owner_type = Column(String(20), nullable=False)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    capabilities = Column(JSONB, nullable=False, default=list)
    approval_status = Column(
        String(30),
        nullable=False,
        default="pending_approval",
        index=True,
    )
    status = Column(String(20), nullable=False, default="paused", index=True)
    is_default = Column(Boolean, nullable=False, default=False)
    ai_mode = Column(String(30), nullable=False, default="suggestion")
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(100), nullable=True)
    last_error_detail = Column(Text, nullable=True)
    asset_metadata = Column(JSONB, nullable=False, default=dict)

    connection = relationship("MetaConnection", back_populates="assets")
    owner_user = relationship("User", foreign_keys=[owner_user_id])
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    credentials = relationship(
        "MetaCredential",
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("asset_type", "external_id", name="uq_meta_asset_external"),
        CheckConstraint(
            "owner_type IN ('broker', 'user')",
            name="ck_meta_asset_owner_type",
        ),
        CheckConstraint(
            "(owner_type = 'broker' AND owner_user_id IS NULL) OR "
            "(owner_type = 'user' AND owner_user_id IS NOT NULL)",
            name="ck_meta_asset_owner_user",
        ),
        CheckConstraint(
            "approval_status IN ('pending_approval', 'approved', 'rejected')",
            name="ck_meta_asset_approval_status",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'disabled', 'error')",
            name="ck_meta_asset_status",
        ),
        CheckConstraint(
            "ai_mode IN ('suggestion', 'supervised_auto', 'human')",
            name="ck_meta_asset_ai_mode",
        ),
        Index("idx_meta_assets_broker_channel", "broker_id", "channel"),
        Index("idx_meta_assets_connection_type", "connection_id", "asset_type"),
    )


class MetaCredential(Base, IdMixin, TimestampMixin):
    """Encrypted credential for a connection or one derived asset."""

    __tablename__ = "meta_credentials"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey("meta_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        Integer,
        ForeignKey("meta_assets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    subject_type = Column(String(40), nullable=False)
    subject_external_id = Column(String(255), nullable=False)
    encrypted_token = Column(Text, nullable=False)
    token_type = Column(String(40), nullable=False, default="bearer")
    scopes = Column(JSONB, nullable=False, default=list)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    key_version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="active", index=True)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)

    connection = relationship("MetaConnection", back_populates="credentials")
    asset = relationship("MetaAsset", back_populates="credentials")

    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "subject_type",
            "subject_external_id",
            name="uq_meta_credential_subject",
        ),
        Index("idx_meta_credentials_broker_status", "broker_id", "status"),
    )


class MetaMessageTemplate(Base, IdMixin, TimestampMixin):
    """Broker-scoped WhatsApp template synchronized from a WABA."""

    __tablename__ = "meta_message_templates"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id = Column(
        Integer,
        ForeignKey("meta_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    waba_external_id = Column(String(255), nullable=False, index=True)
    external_id = Column(String(255), nullable=False)
    name = Column(String(512), nullable=False, index=True)
    language = Column(String(20), nullable=False)
    category = Column(String(50), nullable=True)
    status = Column(String(40), nullable=False, index=True)
    components = Column(JSONB, nullable=False, default=list)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "broker_id",
            "waba_external_id",
            "name",
            "language",
            name="uq_meta_message_template_name_language",
        ),
        Index(
            "idx_meta_message_templates_lookup",
            "broker_id",
            "waba_external_id",
            "status",
        ),
    )


class ChannelIdentity(Base, IdMixin, TimestampMixin):
    """An external person scoped to one business asset and channel."""

    __tablename__ = "channel_identities"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        Integer,
        ForeignKey("meta_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel = Column(String(30), nullable=False, index=True)
    external_user_id = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    first_interaction_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True, index=True)
    identity_metadata = Column(JSONB, nullable=False, default=dict)

    asset = relationship("MetaAsset", foreign_keys=[asset_id])
    lead = relationship("Lead", foreign_keys=[lead_id])

    __table_args__ = (
        UniqueConstraint(
            "broker_id",
            "asset_id",
            "channel",
            "external_user_id",
            name="uq_channel_identity_external",
        ),
        Index("idx_channel_identities_lead_channel", "lead_id", "channel"),
    )


class MetaWebhookEvent(Base, IdMixin, TimestampMixin):
    """Durable idempotent inbox for incoming Meta webhooks."""

    __tablename__ = "meta_webhook_events"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    asset_id = Column(
        Integer,
        ForeignKey("meta_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider = Column(String(30), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    external_event_id = Column(String(255), nullable=True)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    signature_verified = Column(Boolean, nullable=False, default=False)
    payload_ciphertext = Column(Text, nullable=True)
    payload_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    asset = relationship("MetaAsset", foreign_keys=[asset_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed', 'ignored')",
            name="ck_meta_webhook_event_status",
        ),
        Index("idx_meta_webhook_events_processing", "status", "created_at"),
        Index("idx_meta_webhook_events_broker_provider", "broker_id", "provider"),
    )


class MetaAssignmentConflict(Base, IdMixin, TimestampMixin):
    """Manual review when a lead contacts an asset owned by another executive."""

    __tablename__ = "meta_assignment_conflicts"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        Integer,
        ForeignKey("meta_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_assignee_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default="open", index=True)
    resolved_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution = Column(String(40), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead", foreign_keys=[lead_id])
    asset = relationship("MetaAsset", foreign_keys=[asset_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')",
            name="ck_meta_assignment_conflict_status",
        ),
        Index("idx_meta_assignment_conflicts_broker_status", "broker_id", "status"),
    )
