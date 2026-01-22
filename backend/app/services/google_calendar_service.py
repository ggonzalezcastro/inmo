from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import os
import json
import pickle
from app.config import settings
import pytz

logger = logging.getLogger(__name__)

# Scopes necesarios para Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarService:
    """Service for Google Calendar API integration"""
    
    CHILE_TZ = pytz.timezone('America/Santiago')
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar service"""
        try:
            # Opción 1: Usar Service Account (recomendado para producción)
            if settings.GOOGLE_CREDENTIALS_PATH and os.path.exists(settings.GOOGLE_CREDENTIALS_PATH):
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CREDENTIALS_PATH,
                    scopes=SCOPES
                )
                self.service = build('calendar', 'v3', credentials=creds)
                logger.info("Google Calendar service initialized with service account")
                return
            
            # Opción 2: Usar OAuth2 con refresh token
            if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
                creds = self._get_oauth_credentials()
                if creds:
                    self.service = build('calendar', 'v3', credentials=creds)
                    logger.info("Google Calendar service initialized with OAuth2")
                    return
            
            logger.warning("Google Calendar credentials not configured. Meet URLs will not be generated.")
            self.service = None
            
        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {str(e)}", exc_info=True)
            self.service = None
    
    def _get_oauth_credentials(self) -> Optional[Credentials]:
        """Get OAuth2 credentials, refreshing if necessary"""
        creds = None
        token_file = 'token.pickle'
        
        # Cargar token guardado si existe
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # Si no hay credenciales válidas, intentar usar refresh token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Guardar el token actualizado
                    with open(token_file, 'wb') as token:
                        pickle.dump(creds, token)
                    return creds
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
            
            # Si hay refresh token en configuración, usarlo
            if settings.GOOGLE_REFRESH_TOKEN:
                from google.oauth2.credentials import Credentials
                creds = Credentials(
                    token=None,
                    refresh_token=settings.GOOGLE_REFRESH_TOKEN,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=settings.GOOGLE_CLIENT_ID,
                    client_secret=settings.GOOGLE_CLIENT_SECRET,
                    scopes=SCOPES
                )
                # Refrescar el token
                try:
                    creds.refresh(Request())
                    with open(token_file, 'wb') as token:
                        pickle.dump(creds, token)
                    return creds
                except Exception as e:
                    logger.error(f"Error refreshing token from settings: {str(e)}")
            
            logger.warning("No valid OAuth credentials found. Please run authentication flow.")
            return None
        
        return creds
    
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
        Create a Google Calendar event with Google Meet link
        
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
            
            # Construir el evento
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
            
            # Crear el evento
            created_event = self.service.events().insert(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                body=event,
                conferenceDataVersion=1  # Importante: esto crea el Meet link
            ).execute()
            
            # Extraer el link de Google Meet
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
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an existing Google Calendar event"""
        if not self.service:
            return None
        
        try:
            # Obtener el evento existente
            event = self.service.events().get(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                eventId=event_id
            ).execute()
            
            # Actualizar campos
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
            
            # Actualizar el evento
            updated_event = self.service.events().update(
                calendarId=settings.GOOGLE_CALENDAR_ID,
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
                calendarId=settings.GOOGLE_CALENDAR_ID,
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


# Instancia global del servicio
_google_calendar_service = None

def get_google_calendar_service() -> GoogleCalendarService:
    """Get or create Google Calendar service instance"""
    global _google_calendar_service
    if _google_calendar_service is None:
        _google_calendar_service = GoogleCalendarService()
    return _google_calendar_service



