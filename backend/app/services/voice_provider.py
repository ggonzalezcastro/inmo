"""
Voice provider abstraction for making phone calls
Supports multiple providers (Twilio, Telnyx, etc.)
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class VoiceProvider(ABC):
    """Abstract base class for voice providers"""
    
    @abstractmethod
    async def make_call(
        self,
        phone: str,
        from_number: str,
        webhook_url: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Make an outbound call
        
        Args:
            phone: Phone number to call (E.164 format)
            from_number: Phone number to call from
            webhook_url: URL to receive call status webhooks
            context: Additional context (campaign_id, lead_id, etc.)
        
        Returns:
            External call ID from provider
        """
        pass
    
    @abstractmethod
    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        Get current status of a call
        
        Args:
            call_id: External call ID from provider
        
        Returns:
            Dict with call status information
        """
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle webhook from provider
        
        Args:
            payload: Webhook payload from provider
        
        Returns:
            Dict with parsed event information
        """
        pass


class TwilioProvider(VoiceProvider):
    """Twilio voice provider implementation"""
    
    def __init__(self):
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioException
        
        self.account_sid = settings.TWILIO_ACCOUNT_SID if hasattr(settings, 'TWILIO_ACCOUNT_SID') else None
        self.auth_token = settings.TWILIO_AUTH_TOKEN if hasattr(settings, 'TWILIO_AUTH_TOKEN') else None
        self.from_number = settings.TWILIO_PHONE_NUMBER if hasattr(settings, 'TWILIO_PHONE_NUMBER') else None
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Twilio credentials not configured")
            self.client = None
        else:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized")
            except Exception as e:
                logger.error(f"Error initializing Twilio client: {str(e)}")
                self.client = None
    
    async def make_call(
        self,
        phone: str,
        from_number: str,
        webhook_url: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Make outbound call via Twilio"""
        
        if not self.client:
            raise ValueError("Twilio client not initialized. Check credentials.")
        
        try:
            # Build TwiML URL or use webhook for call handling
            call = self.client.calls.create(
                to=phone,
                from_=from_number or self.from_number,
                url=webhook_url,  # TwiML URL for call flow
                status_callback=webhook_url,  # Status updates
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                method='POST'
            )
            
            logger.info(f"Twilio call initiated: {call.sid} to {phone}")
            return call.sid
        
        except Exception as e:
            logger.error(f"Error making Twilio call: {str(e)}", exc_info=True)
            raise
    
    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Get call status from Twilio"""
        
        if not self.client:
            raise ValueError("Twilio client not initialized")
        
        try:
            call = self.client.calls(call_id).fetch()
            
            return {
                "call_id": call.sid,
                "status": call.status,
                "duration": int(call.duration) if call.duration else None,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None,
                "direction": call.direction,
                "from": call.from_,
                "to": call.to,
                "recording_url": call.subresource_uris.get("recordings") if hasattr(call, 'subresource_uris') else None
            }
        
        except Exception as e:
            logger.error(f"Error getting Twilio call status: {str(e)}", exc_info=True)
            raise
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Twilio webhook"""
        
        call_sid = payload.get("CallSid")
        call_status = payload.get("CallStatus")
        call_duration = payload.get("CallDuration")
        
        event_type = None
        if call_status == "initiated":
            event_type = "initiated"
        elif call_status == "ringing":
            event_type = "ringing"
        elif call_status == "answered":
            event_type = "answered"
        elif call_status == "completed":
            event_type = "completed"
        elif call_status in ["failed", "busy", "no-answer"]:
            event_type = "failed"
        
        return {
            "event_type": event_type,
            "call_id": call_sid,
            "status": call_status,
            "duration": int(call_duration) if call_duration else None,
            "from": payload.get("From"),
            "to": payload.get("To"),
            "recording_url": payload.get("RecordingUrl"),
            "raw": payload
        }


class TelnyxProvider(VoiceProvider):
    """Telnyx voice provider implementation"""
    
    def __init__(self):
        try:
            import telnyx
            self.api_key = settings.TELNYX_API_KEY if hasattr(settings, 'TELNYX_API_KEY') else None
            
            if not self.api_key:
                logger.warning("Telnyx API key not configured")
                self.client = None
            else:
                telnyx.api_key = self.api_key
                self.client = telnyx
                logger.info("Telnyx client initialized")
        except ImportError:
            logger.warning("Telnyx SDK not installed")
            self.client = None
        except Exception as e:
            logger.error(f"Error initializing Telnyx client: {str(e)}")
            self.client = None
    
    async def make_call(
        self,
        phone: str,
        from_number: str,
        webhook_url: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Make outbound call via Telnyx"""
        
        if not self.client:
            raise ValueError("Telnyx client not initialized. Check API key.")
        
        # Telnyx implementation would go here
        # For now, raise NotImplementedError
        raise NotImplementedError("Telnyx provider not yet implemented")


def get_voice_provider() -> VoiceProvider:
    """Get configured voice provider instance"""
    
    provider_name = getattr(settings, 'VOICE_PROVIDER', 'twilio').lower()
    
    if provider_name == 'twilio':
        return TwilioProvider()
    elif provider_name == 'telnyx':
        return TelnyxProvider()
    else:
        logger.warning(f"Unknown voice provider: {provider_name}, defaulting to Twilio")
        return TwilioProvider()



