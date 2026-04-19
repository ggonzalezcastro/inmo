#!/usr/bin/env python3
"""
Temporary script to refactor llm_service.py to use structured messages
This will be run and then deleted
"""

import re
import sys

def refactor_build_llm_prompt(content):
    """Replace build_llm_prompt function with structured version"""
    
    old_function = r'(@staticmethod\s+async def build_llm_prompt\([^)]+\) -> str:[^@]+?return f"{system_prompt}\\n\\n{context_summary}")'
    
    new_function = '''@staticmethod
    async def build_llm_prompt(
        lead_context: Dict,
        new_message: str,
        db: Optional[AsyncSession] = None,
        broker_id: Optional[int] = None
    ) -> Tuple[str, List[types.Content]]:
        """
        Build LLM prompt with lead context, optionally using broker configuration.
        Returns (system_prompt, message_history) for structured API usage.
        
        Args:
            lead_context: Lead context dictionary with message_history as structured array
            new_message: New message from user
            db: Optional database session
            broker_id: Optional broker ID for configuration
            
        Returns:
            Tuple of (system_prompt, contents_list) where contents_list is ready for Gemini API
        """
        
        # Get system prompt from broker config or default
        system_prompt = None
        if broker_id and db:
            try:
                from app.services.broker import BrokerConfigService
                system_prompt = await BrokerConfigService.build_system_prompt(
                    db, broker_id, lead_context
                )
            except Exception as e:
                if db:
                    await db.rollback()
                logger.warning(f"Could not load broker config for broker_id {broker_id}: {e}")
        
        # Fallback to default if broker config not available
        if not system_prompt:
            from app.services.broker import BrokerConfigService
            system_prompt = BrokerConfigService.DEFAULT_SYSTEM_PROMPT
        
        # Get message history - prefer structured format, fallback to legacy
        message_history = lead_context.get('message_history', [])
        if isinstance(message_history, str):
            # Legacy format - convert to structured
            logger.warning("[LLM] Using legacy message_history format, converting...")
            message_history = []
            parts = lead_context.get('message_history_legacy', '').split('|')
            for part in parts:
                if ':' in part:
                    prefix, content = part.split(':', 1)
                    role = "user" if prefix == "U" else "assistant"
                    message_history.append({"role": role, "content": content})
        
        # Build structured contents for Gemini API
        contents = []
        
        # Add conversation history (structured messages)
        for msg in message_history:
            role = msg.get("role", "user")
            content_text = msg.get("content", "")
            
            # Map roles: user -> "user", assistant -> "model" (Gemini format)
            gemini_role = "user" if role == "user" else "model"
            contents.append(types.Content(
                role=gemini_role,
                parts=[types.Part(text=content_text)]
            ))
        
        # Add new message from user
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=new_message)]
        ))
        
        # Add context summary as a final system instruction
        context_summary = LLMService._build_context_summary(lead_context, new_message)
        
        # Enhance system prompt with context summary
        enhanced_system_prompt = f"{system_prompt}\\n\\n{context_summary}"
        
        return enhanced_system_prompt, contents'''
    
    # This is a complex regex replacement - let's do it manually
    return content  # Will handle manually

if __name__ == "__main__":
    print("This script will refactor llm_service.py")
    print("Please run the changes manually due to complexity")
