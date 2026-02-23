"""
Chat utilities and helpers.

Extracted from chat.py to improve modularity and testability.
"""
from typing import List, Dict, Optional
from datetime import datetime


class InterestDetector:
    """
    Detects positive interest confirmations in user messages.
    
    This class encapsulates the logic for determining if a user
    has confirmed interest in the service, based on their response
    to bot questions.
    """
    
    # Known positive confirmation responses
    POSITIVE_RESPONSES = frozenset([
        "si", "sí", "yes", "claro", "por supuesto", "obvio", 
        "porfavor", "por favor", "dale", "ok", "okay", "va", 
        "si porfavor", "sí por favor", "yes please", "bueno",
        "está bien", "esta bien", "de acuerdo", "perfecto",
        "genial", "excelente", "listo", "vale", "venga"
    ])
    
    # Patterns that indicate positive response when message starts with these
    POSITIVE_PREFIXES = ("si", "sí", "yes", "claro", "ok")
    
    # Keywords in bot messages that indicate interest-related questions
    INTEREST_KEYWORDS = [
        "interes", "calificas", "sigues buscando", 
        "te gustaría", "te interesa", "quieres"
    ]
    
    @classmethod
    def is_positive_confirmation(cls, message: str) -> bool:
        """
        Check if a message is a positive confirmation.
        
        Args:
            message: The user's message text
            
        Returns:
            True if message indicates positive confirmation
        """
        if not message:
            return False
            
        normalized = message.lower().strip()
        
        # Exact match with known positive responses
        if normalized in cls.POSITIVE_RESPONSES:
            return True
        
        # Check for positive prefix with partial match
        if any(normalized.startswith(prefix + " ") for prefix in cls.POSITIVE_PREFIXES):
            return True
        
        # Short messages starting with "si" or "sí" 
        if (normalized.startswith("si") or normalized.startswith("sí")) and len(normalized) <= 10:
            return True
        
        return False
    
    @classmethod
    def bot_asked_about_interest(cls, message_history: List[Dict]) -> bool:
        """
        Check if the bot's last message asked about interest.
        
        Args:
            message_history: List of message dicts with 'role' and 'content'
            
        Returns:
            True if last bot message contained interest-related question
        """
        if not message_history:
            return False
        
        # Handle structured format (list of dicts)
        if isinstance(message_history, list):
            for msg in reversed(message_history):
                role = msg.get("role", "")
                content = msg.get("content", "")
                
                if role == "assistant" and content:
                    content_lower = content.lower()
                    if any(keyword in content_lower for keyword in cls.INTEREST_KEYWORDS):
                        return True
                    break  # Only check last assistant message
        
        # Handle legacy format (pipe-separated string)
        elif isinstance(message_history, str):
            for keyword in cls.INTEREST_KEYWORDS:
                if keyword in message_history.lower():
                    return True
        
        return False
    
    @classmethod
    def check_interest_confirmed(
        cls, 
        message: str, 
        message_history: List[Dict],
        current_metadata: Dict
    ) -> Dict:
        """
        Check if user confirmed interest and update metadata accordingly.
        
        Args:
            message: Current user message
            message_history: Conversation history
            current_metadata: Current lead metadata dict
            
        Returns:
            Updated metadata dict (may include interest_confirmed fields)
        """
        is_positive = cls.is_positive_confirmation(message)
        bot_asked = cls.bot_asked_about_interest(message_history)
        
        if is_positive and bot_asked:
            current_metadata["interest_confirmed"] = True
            current_metadata["interest_confirmed_at"] = datetime.now().isoformat()
        
        return current_metadata


class LeadDataExtractor:
    """
    Utility class for checking completeness of lead data.
    """
    
    @staticmethod
    def has_complete_info(lead) -> bool:
        """
        Check if lead has all required information for qualification.
        
        Args:
            lead: Lead ORM object
            
        Returns:
            True if all required fields are populated
        """
        # Check name
        if not lead.name or lead.name in ['User', 'Test User']:
            return False
        
        # Check phone (exclude placeholders)
        phone = str(lead.phone) if lead.phone else ""
        if not phone or phone.startswith(('web_chat_', 'whatsapp_', '+569999')):
            return False
        
        # Check email
        if not lead.email or not str(lead.email).strip():
            return False
        
        # Check metadata fields
        metadata = lead.lead_metadata or {}
        if not metadata.get('location'):
            return False
        
        # Budget OR salary should be present
        if not metadata.get('budget') and not metadata.get('salary') and not metadata.get('monthly_income'):
            return False
        
        return True
    
    @staticmethod
    def get_missing_fields(lead) -> List[str]:
        """
        Get list of missing required fields.
        
        Args:
            lead: Lead ORM object
            
        Returns:
            List of field names that are missing
        """
        missing = []
        
        if not lead.name or lead.name in ['User', 'Test User']:
            missing.append("name")
        
        phone = str(lead.phone) if lead.phone else ""
        if not phone or phone.startswith(('web_chat_', 'whatsapp_', '+569999')):
            missing.append("phone")
        
        if not lead.email or not str(lead.email).strip():
            missing.append("email")
        
        metadata = lead.lead_metadata or {}
        
        if not metadata.get('location'):
            missing.append("location")
        
        if not metadata.get('budget') and not metadata.get('salary') and not metadata.get('monthly_income'):
            missing.append("income")
        
        if not metadata.get('dicom_status'):
            missing.append("dicom_status")
        
        return missing
