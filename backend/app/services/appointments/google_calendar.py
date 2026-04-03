from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import os
import pytz
from app.config import settings

logger = logging.getLogger(__name__)

# Scopes necesarios para Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarService:
    """Service for Google Calendar API integration"""

    CHILE_TZ = pytz.timezone('America/Santiago')

    def __init__(self, refresh_token: Optional[str] = None, calendar_id: Optional[str] = None):
        """
        Initialize with optional per-broker credentials.
        Falls back to global settings if not provided.
        """
        self.service = None
        self.calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID or "primary"
        self._initialize_service(refresh_token)

    @property
    def is_ready(self) -> bool:
        """True when the underlying Google API client is initialized."""
        return self.service is not None

    def _initialize_service(self, refresh_token: Optional[str] = None):
        """Initialize Google Calendar service"""
        try:
            # Opción 1: Service Account (recomendado para producción)
            if settings.GOOGLE_CREDENTIALS_PATH and os.path.exists(settings.GOOGLE_CREDENTIALS_PATH):
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CREDENTIALS_PATH,
                    scopes=SCOPES
                )
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar service initialized with service account")
                return

            # Opción 2: Refresh token (por broker o global desde settings)
            effective_token = refresh_token or settings.GOOGLE_REFRESH_TOKEN
            if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and effective_token:
                creds = self._build_credentials(effective_token)
                if creds:
                    self.service = build('calendar', 'v3', credentials=creds)
                    logger.info("Google Calendar service initialized with OAuth2")
                    return

            logger.warning("Google Calendar credentials not configured. Meet URLs will not be generated.")
            self.service = None

        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {str(e)}", exc_info=True)
            self.service = None

    def _build_credentials(self, refresh_token: str) -> Optional[Credentials]:
        """Build and refresh OAuth2 credentials from a refresh token."""
        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=SCOPES,
            )
            creds.refresh(Request())
            return creds
        except Exception as e:
            logger.error(f"Error refreshing Google OAuth token: {str(e)}")
            return None

    def create_event_with_meet(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        attendees: Optional[list] = None,
        location: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Google Calendar event with Google Meet link.

        Returns:
            Dict with event details including 'meet_url' and 'event_id', or None if failed
        """
        if not self.service:
            logger.warning("Google Calendar service not available")
            return None

        try:
            # Asegurar que las fechas estén en formato correcto
            if start_time.tzinfo is None:
                start_time = self.CHILE_TZ.localize(start_time)
            if end_time.tzinfo is None:
                end_time = self.CHILE_TZ.localize(end_time)

            # Convertir a UTC para Google Calendar
            start_time_utc = start_time.astimezone(pytz.UTC)
            end_time_utc = end_time.astimezone(pytz.UTC)

            event = {
                'summary': title,
                'description': description or '',
                'start': {
                    'dateTime': start_time_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"meet-{start_time_utc.timestamp()}",
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                },
                'attendees': [{'email': email} for email in (attendees or [])],
            }

            if location:
                event['location'] = location

            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                conferenceDataVersion=1
            ).execute()

            meet_url = None
            if 'conferenceData' in created_event:
                entry_points = created_event['conferenceData'].get('entryPoints', [])
                for entry_point in entry_points:
                    if entry_point.get('entryPointType') == 'video':
                        meet_url = entry_point.get('uri')
                        break

            logger.info(f"Google Calendar event created: {created_event.get('id')}")

            return {
                'event_id': created_event.get('id'),
                'meet_url': meet_url,
                'html_link': created_event.get('htmlLink'),
                'start_time': start_time_utc.isoformat(),
                'end_time': end_time_utc.isoformat()
            }

        except HttpError as e:
            logger.error(f"Error creating Google Calendar event: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Google Calendar event: {str(e)}", exc_info=True)
            return None

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        attendees: Optional[list] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an existing Google Calendar event"""
        if not self.service:
            return None

        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()

            if title:
                event['summary'] = title
            if description:
                event['description'] = description
            if start_time:
                if start_time.tzinfo is None:
                    start_time = self.CHILE_TZ.localize(start_time)
                start_time_utc = start_time.astimezone(pytz.UTC)
                event['start'] = {
                    'dateTime': start_time_utc.isoformat(),
                    'timeZone': 'UTC',
                }
            if end_time:
                if end_time.tzinfo is None:
                    end_time = self.CHILE_TZ.localize(end_time)
                end_time_utc = end_time.astimezone(pytz.UTC)
                event['end'] = {
                    'dateTime': end_time_utc.isoformat(),
                    'timeZone': 'UTC',
                }
            if attendees is not None:
                event['attendees'] = [{'email': email} for email in attendees]

            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()

            logger.info(f"Google Calendar event updated: {event_id}")
            return updated_event

        except HttpError as e:
            logger.error(f"Error updating Google Calendar event: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error updating Google Calendar event: {str(e)}", exc_info=True)
            return None

    def delete_event(self, event_id: str) -> bool:
        """Delete a Google Calendar event"""
        if not self.service:
            return False

        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()

            logger.info(f"Google Calendar event deleted: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Error deleting Google Calendar event: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting Google Calendar event: {str(e)}", exc_info=True)
            return False


# Instancia global (fallback cuando un broker no tiene credenciales propias)
_google_calendar_service = None


def get_google_calendar_service() -> GoogleCalendarService:
    """Get or create the global Google Calendar service instance (uses settings)."""
    global _google_calendar_service
    if _google_calendar_service is None:
        _google_calendar_service = GoogleCalendarService()
    return _google_calendar_service


def get_calendar_service_for_broker(broker_config):
    """
    Return the appropriate calendar service for the given broker.

    Checks `broker_config.calendar_provider`:
      - 'outlook' → OutlookCalendarService (Microsoft Graph)
      - 'google' or None → GoogleCalendarService (default)

    Falls back to the global Google service when no credentials are present.
    """
    from app.core.encryption import decrypt_value

    provider = getattr(broker_config, "calendar_provider", None) or "google"

    if provider == "outlook":
        outlook_rt = getattr(broker_config, "outlook_refresh_token", None)
        if outlook_rt:
            from app.services.appointments.outlook_calendar import OutlookCalendarService
            token = decrypt_value(outlook_rt)
            calendar_id = getattr(broker_config, "outlook_calendar_id", None)
            return OutlookCalendarService(refresh_token=token, calendar_id=calendar_id)
        logger.warning(
            "calendar_provider='outlook' but no refresh token found for broker_id=%s; "
            "falling back to Google",
            getattr(broker_config, "broker_id", "?"),
        )

    # Google (default)
    if broker_config and getattr(broker_config, "google_refresh_token", None):
        token = decrypt_value(broker_config.google_refresh_token)
        calendar_id = broker_config.google_calendar_id or "primary"
        return GoogleCalendarService(refresh_token=token, calendar_id=calendar_id)

    return get_google_calendar_service()


def get_calendar_service_for_agent(agent, broker_config):
    """
    Return a calendar service targeting the agent's own calendar.

    Fallback chain (most specific → least specific):
      1. Agent's personal OAuth token (google_refresh_token / outlook_refresh_token)
      2. Agent's shared calendar via service account (google_calendar_id + GOOGLE_CREDENTIALS_PATH)
      3. Broker's OAuth credentials (google or outlook depending on calendar_provider)
      4. Global OAuth / service account (primary calendar)
    """
    if agent:
        from app.core.encryption import decrypt_value as _decrypt

        # 1. Agent's personal Google OAuth token
        if getattr(agent, "google_refresh_token", None):
            try:
                token = _decrypt(agent.google_refresh_token)
                svc = GoogleCalendarService(
                    refresh_token=token,
                    calendar_id=agent.google_calendar_email or "primary",
                )
                if svc.is_ready:
                    logger.info(
                        "Using per-agent Google OAuth token for agent_id=%s (%s)",
                        agent.id, agent.google_calendar_email,
                    )
                    return svc
            except Exception as exc:
                logger.warning("Failed to build per-agent Google service for agent %s: %s", agent.id, exc)

        # 1b. Agent's personal Outlook OAuth token
        if getattr(agent, "outlook_refresh_token", None):
            try:
                from app.services.appointments.outlook_calendar import OutlookCalendarService
                token = _decrypt(agent.outlook_refresh_token)
                svc = OutlookCalendarService(
                    refresh_token=token,
                    calendar_id=agent.outlook_calendar_id,
                )
                if svc.is_ready:
                    logger.info(
                        "Using per-agent Outlook OAuth token for agent_id=%s (%s)",
                        agent.id, agent.outlook_calendar_email,
                    )
                    return svc
            except Exception as exc:
                logger.warning("Failed to build per-agent Outlook service for agent %s: %s", agent.id, exc)

        # 2. Agent's shared calendar via service account
        if getattr(agent, "google_calendar_id", None) and agent.google_calendar_connected:
            if settings.GOOGLE_CREDENTIALS_PATH and os.path.exists(settings.GOOGLE_CREDENTIALS_PATH):
                svc = GoogleCalendarService(calendar_id=agent.google_calendar_id)
                if svc.service:
                    logger.info(
                        "Using service account for agent calendar_id=%s (agent_id=%s)",
                        agent.google_calendar_id, agent.id,
                    )
                    return svc

    # 3 & 4. Fallback to broker / global calendar
    return get_calendar_service_for_broker(broker_config)
