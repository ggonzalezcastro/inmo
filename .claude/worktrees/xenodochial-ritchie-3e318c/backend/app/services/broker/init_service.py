"""
Service for initializing broker data when a new user registers
Creates Broker, BrokerPromptConfig, and BrokerLeadConfig automatically
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
import logging
import re

from app.models.broker import Broker, BrokerPromptConfig, BrokerLeadConfig
from app.models.broker_voice_config import BrokerVoiceConfig
from app.models.user import User, UserRole
from app.services.broker.config_service import BrokerConfigService

logger = logging.getLogger(__name__)


class BrokerInitService:
    """Service for initializing broker configuration when user registers"""

    @staticmethod
    async def initialize_broker_for_user(
        db: AsyncSession,
        user: User,
        broker_name: str
    ) -> Optional[Broker]:
        """
        Create broker and default configurations for a new user

        Args:
            db: Database session
            user: User object
            broker_name: Name of the broker

        Returns:
            Created Broker object or None if error
        """
        try:
            # Generate slug from broker name
            slug = re.sub(r'[^a-z0-9]+', '-', broker_name.lower()).strip('-')

            # Check if broker with same slug exists
            result = await db.execute(
                select(Broker).where(Broker.slug == slug)
            )
            existing = result.scalars().first()

            if existing:
                # If broker exists, use it
                logger.info(f"Broker with slug '{slug}' already exists, using existing broker")
                broker = existing
            else:
                # Create new broker
                broker = Broker(
                    name=broker_name,
                    slug=slug,
                    email=user.email,
                    is_active=True,
                    country="Chile",
                    language="es",
                    currency="CLP",
                    timezone="America/Santiago"
                )

                db.add(broker)
                await db.commit()
                await db.refresh(broker)

                logger.info(f"Created broker: {broker.id} - {broker.name}")

            # Check if prompt config already exists
            result = await db.execute(
                select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == broker.id)
            )
            existing_prompt_config = result.scalars().first()

            if not existing_prompt_config:
                # Create default prompt config using the main DEFAULT_SYSTEM_PROMPT
                prompt_config = BrokerPromptConfig(
                    broker_id=broker.id,
                    agent_name="Sofía",
                    agent_role="asistente de calificación de leads",
                    full_custom_prompt=BrokerConfigService.DEFAULT_SYSTEM_PROMPT,
                    enable_appointment_booking=True
                )
                db.add(prompt_config)
                logger.info(f"Created default prompt config for broker {broker.id} using DEFAULT_SYSTEM_PROMPT")

            # Check if lead config already exists
            result = await db.execute(
                select(BrokerLeadConfig).where(BrokerLeadConfig.broker_id == broker.id)
            )
            existing_lead_config = result.scalars().first()

            if not existing_lead_config:
                lead_config = BrokerLeadConfig(
                    broker_id=broker.id
                )
                db.add(lead_config)
                logger.info(f"Created default lead config for broker {broker.id}")

            # Check if voice config already exists
            result = await db.execute(
                select(BrokerVoiceConfig).where(BrokerVoiceConfig.broker_id == broker.id)
            )
            existing_voice_config = result.scalars().first()

            if not existing_voice_config:
                voice_config = BrokerVoiceConfig(
                    broker_id=broker.id,
                    recording_enabled=True,
                )
                db.add(voice_config)
                logger.info(f"Created default voice config for broker {broker.id}")

            # Update user with broker_id and set role to ADMIN (owner)
            user.broker_id = broker.id
            user.role = UserRole.ADMIN

            await db.commit()
            await db.refresh(user)

            logger.info(f"User {user.email} assigned to broker {broker.id} as ADMIN")

            return broker

        except Exception as e:
            await db.rollback()
            logger.error(f"Error initializing broker for user {user.email}: {e}")
            raise
