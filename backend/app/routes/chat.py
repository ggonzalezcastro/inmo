from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.telegram_service import TelegramService
from app.services.lead_context_service import LeadContextService
from app.services.llm_service import LLMService
from app.services.activity_service import ActivityService
from app.services.lead_service import LeadService
from app.services.agent_tools_service import AgentToolsService
from app.models.lead import Lead, LeadStatus
from google.genai import types
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    message: str
    lead_id: Optional[int] = None  # Optional, will create new lead if not provided


class ChatResponse(BaseModel):
    response: str
    lead_id: int
    lead_score: float
    lead_status: str


@router.post("/test", response_model=ChatResponse)
async def test_chat(
    chat_message: ChatMessage,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test chat endpoint - simulates Telegram message processing"""
    
    logger.info(f"[CHAT] test_chat called - Message: '{chat_message.message}', Lead ID: {chat_message.lead_id}")
    
    try:
        # If lead_id provided, get existing lead, otherwise create new
        if chat_message.lead_id:
            lead = await LeadService.get_lead(db, chat_message.lead_id)
            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")
        else:
            # Create a new lead without phone - will be captured during conversation
            from app.schemas.lead import LeadCreate
            
            # Use a placeholder that indicates it's not a real phone
            # The phone will be updated when captured during the conversation
            # Note: Must be <= 20 chars to fit in VARCHAR(20)
            lead_data = LeadCreate(
                phone="web_chat_pending",  # Placeholder identificable (16 chars, fits in VARCHAR(20))
                name=None,  # Sin nombre hasta que se capture
                tags=["test", "chat", "web_chat"]
            )
            lead = await LeadService.create_lead(db, lead_data)
            
        current_lead_id = lead.id  # Store ID locally to avoid MissingGreenlet on expired objects
        
        # Log inbound message (web chat - user_id=0 indicates web, not telegram)
        await ActivityService.log_telegram_message(
            db,
            lead_id=lead.id,
            telegram_user_id=0,  # 0 = web chat (not telegram)
            message_text=chat_message.message,
            direction="in"
        )
        
        # Refresh lead to prevent MissingGreenlet error (commit in log_telegram_message expires the object)
        await db.refresh(lead)
        
        # Get lead context initially
        logger.info(f"[CHAT] Getting lead context for lead_id: {lead.id}")
        context = await LeadContextService.get_lead_context(db, lead.id)
        
        # --- ANALYZE AND UPDATE LEAD FIRST ---
        # Analyze lead qualification based on new message
        logger.info("[CHAT] Analyzing lead qualification...")
        analysis = await LLMService.analyze_lead_qualification(chat_message.message, context)
        logger.info(f"[CHAT] Analysis result: {analysis}")
        
        # Calculate new score
        # Refresh lead before accessing attributes to avoid MissingGreenlet
        await db.refresh(lead)
        old_score = lead.lead_score
        score_delta = analysis.get("score_delta", 0)
        new_score = max(0, min(100, old_score + score_delta))
        
        lead.lead_score = new_score
        
        # Update fields if found
        if analysis.get("name"):
            lead.name = analysis["name"]
        if analysis.get("phone"):
            lead.phone = analysis["phone"]
        if analysis.get("email"):
            lead.email = analysis["email"]
            
        # Update metadata
        current_metadata = dict(lead.lead_metadata or {})
        
        # Update specific metadata fields if present in analysis
        for field in ["location", "timeline", "salary", "job_type", "property_type", "bedrooms", "dicom_status", "morosidad_amount"]:
            if analysis.get(field):
                current_metadata[field] = analysis[field]
                # If updating salary, also update monthly_income for consistency
                if field == "salary":
                    current_metadata["monthly_income"] = analysis[field]
        
        # Detect and save interest confirmation
        # Check if user responded positively to interest-related questions
        message_lower = chat_message.message.lower().strip()
        interest_confirmations = ["si", "sí", "yes", "claro", "por supuesto", "obvio", "porfavor", "por favor", "dale", "ok", "okay", "va", "si porfavor", "sí por favor", "yes please"]
        
        # Check if this looks like a positive confirmation
        is_positive_confirmation = (
            message_lower in interest_confirmations or
            any(confirm in message_lower for confirm in ["si ", "sí ", "yes ", "claro ", "ok "]) or
            (message_lower.startswith("si") and len(message_lower) <= 10) or
            (message_lower.startswith("sí") and len(message_lower) <= 10)
        )
        
        # Check if previous bot message asked about interest
        message_history = context.get('message_history', [])
        bot_asked_about_interest = False
        
        # Handle both structured format (list) and legacy format (string)
        if isinstance(message_history, list):
            # Structured format - search in assistant messages
            for msg in reversed(message_history):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "assistant" and content:
                    content_lower = content.lower()
                    if any(keyword in content_lower for keyword in ["interes", "calificas", "sigues buscando", "te gustaría"]):
                        bot_asked_about_interest = True
                        break
        elif isinstance(message_history, str):
            # Legacy format - search in string
            previous_messages = message_history.lower()
            bot_asked_about_interest = (
                "interes" in previous_messages or
                "calificas" in previous_messages or
                "sigues buscando" in previous_messages or
                "te gustaría" in previous_messages
            )
        
        if is_positive_confirmation and bot_asked_about_interest:
            current_metadata["interest_confirmed"] = True
            current_metadata["interest_confirmed_at"] = datetime.now().isoformat()
            logger.info(f"[CHAT] Interest confirmed by user for lead {lead.id}")
        
        # Handle salary explicitly (don't store budget unless explicitly mentioned)
        if analysis.get("salary") and not analysis.get("budget"):
            current_metadata["monthly_income"] = analysis["salary"]
            current_metadata["salary"] = analysis["salary"]
        
        # Only store budget if explicitly mentioned (not just a number after asking about rent)
        if analysis.get("budget") and "presupuesto" in chat_message.message.lower() or "precio" in chat_message.message.lower() or "valor máximo" in chat_message.message.lower():
            current_metadata["budget"] = analysis["budget"]
                
        # Update key points
        if analysis.get("key_points"):
            current_points = current_metadata.get("key_points", [])
            if not isinstance(current_points, list):
                current_points = []
            # Add new unique points
            for point in analysis["key_points"]:
                if point not in current_points:
                    current_points.append(point)
            current_metadata["key_points"] = current_points
            
        # Update last analysis
        current_metadata["last_analysis"] = analysis
        current_metadata["source"] = "web_chat"
        
        lead.lead_metadata = current_metadata
        
        # Check if we have all required information
        has_all_info = (
            lead.name and lead.name not in ['User', 'Test User'] and
            lead.phone and not str(lead.phone).startswith(('web_chat_', 'whatsapp_', '+569999')) and
            lead.email and str(lead.email).strip() != '' and
            lead.lead_metadata.get('location') and
            lead.lead_metadata.get('budget')
        )
        
        # Auto-update status based on score and completeness
        if has_all_info:
            lead.status = LeadStatus.HOT
        elif new_score < 20:
            lead.status = LeadStatus.COLD
        elif new_score < 50:
            lead.status = LeadStatus.WARM
        else:
            lead.status = LeadStatus.HOT
        
        # Initialize pipeline_stage if not set
        if not lead.pipeline_stage:
            lead.pipeline_stage = "entrada"
            lead.stage_entered_at = datetime.now()
        
        # Commit updates before pipeline operations
        await db.commit()
        await db.refresh(lead)
        
        # Auto-advance pipeline stage if conditions are met
        from app.services.pipeline_service import PipelineService
        try:
            async with db.begin_nested():
                await PipelineService.auto_advance_stage(db, lead.id)
                await db.refresh(lead)
        except Exception as e:
            logger.error(f"Error auto-advancing pipeline stage: {str(e)}")
        
        # Actualizar pipeline stage automáticamente según datos del lead
        try:
            async with db.begin_nested():
                await PipelineService.actualizar_pipeline_stage(db, lead)
                await db.refresh(lead)
        except Exception as e:
            logger.error(f"Error updating pipeline stage: {str(e)}")
            
        # Final commit for updates
        await db.commit()
        await db.refresh(lead)
        
        # --- RE-FETCH CONTEXT AND GENERATE RESPONSE ---
        
        # Re-fetch context with updated data so LLM knows what we have
        context = await LeadContextService.get_lead_context(db, lead.id)
        logger.info(f"[CHAT] Re-fetched context: name={context.get('name')}, phone={context.get('phone')}, email={context.get('email')}, metadata_location={context.get('metadata', {}).get('location')}")
        
        # Build LLM prompt
        logger.info("[CHAT] Building LLM prompt...")
        # Get broker_id from current_user if available
        broker_id = current_user.get("broker_id") if current_user else None
        system_prompt, contents = await LLMService.build_llm_prompt(
            context, 
            chat_message.message,
            db=db,
            broker_id=broker_id
        )
        logger.info(f"[CHAT] System prompt built - Length: {len(system_prompt)} chars")
        logger.info(f"[CHAT] Contents count: {len(contents)} messages")
        
        # Generate response with function calling support
        logger.info("[CHAT] Generating AI response with function calling...")
        
        # Get function declarations for tools
        function_declarations = AgentToolsService.get_function_declarations()
        tools = [types.Tool(function_declarations=function_declarations)]
        
        # Create tool executor that will execute the tools
        async def tool_executor(tool_name: str, arguments: dict):
            """Execute a tool and return the result"""
            try:
                # Use nested transaction for tool execution to prevent main transaction aborts
                async with db.begin_nested():
                    return await AgentToolsService.execute_tool(
                        db=db,
                        tool_name=tool_name,
                        arguments=arguments,
                        lead_id=current_lead_id,
                        agent_id=None  # Will use first available agent
                    )
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                # Return error result so LLM knows it failed, but DB session is safe
                return {"error": str(e), "success": False}
        
        # Generate response with function calling
        ai_response, function_calls = await LLMService.generate_response_with_function_calling(
            system_prompt=system_prompt,
            contents=contents,
            tools=tools,
            tool_executor=tool_executor
        )
        
        # Log function calls if any
        if function_calls:
            logger.info(f"[CHAT] Function calls executed: {len(function_calls)}")
            for fc in function_calls:
                logger.info(f"[CHAT] - Function: {fc.get('name')}, Args: {fc.get('args')}, Success: {fc.get('result', {}).get('success', False)}")
        
        logger.info(f"[CHAT] AI response received - Length: {len(ai_response)} chars")
        logger.info(f"[CHAT] AI response: {ai_response}")
        
        # Log score change
        if new_score != old_score:
            await ActivityService.log_activity(
                db,
                lead_id=current_lead_id,
                action_type="score_update",
                details={
                    "old_score": old_score,
                    "new_score": new_score,
                    "delta": score_delta,
                    "reason": "test_chat",
                    "analysis": analysis
                }
            )
        
        # Log outbound message (web chat)
        await ActivityService.log_telegram_message(
            db,
            lead_id=current_lead_id,
            telegram_user_id=0,  # 0 = web chat (not telegram)
            message_text=ai_response,
            direction="out"
        )
        
        # Log activity
        await ActivityService.log_activity(
            db,
            lead_id=current_lead_id,
            action_type="message",
            details={
                "direction": "in",
                "message": chat_message.message,
                "response": ai_response,
                "ai_used": True
            }
        )
        
        # Refresh lead one last time to get final status safely
        await db.refresh(lead)
        
        return ChatResponse(
            response=ai_response,
            lead_id=current_lead_id,
            lead_score=new_score,
            lead_status=lead.status
        )
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in test chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lead_id}/messages")
async def get_chat_messages(
    lead_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get chat messages for a lead"""
    
    try:
        # Verify lead exists
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get messages for this lead
        from app.models.telegram_message import TelegramMessage
        from sqlalchemy.future import select
        from sqlalchemy import desc
        
        messages_result = await db.execute(
            select(TelegramMessage)
            .where(TelegramMessage.lead_id == lead_id)
            .order_by(TelegramMessage.created_at)
            .offset(skip)
            .limit(limit)
        )
        messages = messages_result.scalars().all()
        
        return {
            "lead_id": lead_id,
            "messages": [
                {
                    "id": msg.id,
                    "direction": msg.direction.value,
                    "message_text": msg.message_text,
                    "sender_type": "bot" if msg.direction.value == "out" else "customer",
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "ai_response_used": msg.ai_response_used or False
                }
                for msg in messages
            ],
            "total": len(messages),
            "skip": skip,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verify/{lead_id}")
async def verify_lead_data(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify that lead data and messages are being saved correctly"""
    
    try:
        # Get lead
        lead = await LeadService.get_lead(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get all messages for this lead
        from app.models.telegram_message import TelegramMessage
        from sqlalchemy.future import select
        from sqlalchemy import desc
        
        messages_result = await db.execute(
            select(TelegramMessage)
            .where(TelegramMessage.lead_id == lead_id)
            .order_by(desc(TelegramMessage.created_at))
        )
        messages = messages_result.scalars().all()
        
        # Get activities
        from app.models.activity_log import ActivityLog
        activities_result = await db.execute(
            select(ActivityLog)
            .where(ActivityLog.lead_id == lead_id)
            .order_by(desc(ActivityLog.timestamp))
            .limit(20)
        )
        activities = activities_result.scalars().all()
        
        # Build response
        return {
            "lead": {
                "id": lead.id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "status": lead.status,
                "lead_score": lead.lead_score,
                "metadata": lead.lead_metadata if lead.lead_metadata else {},
                "metadata_toon": "|".join([f"{k}:{v}" for k, v in (lead.lead_metadata or {}).items() if v]),
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            },
            "messages": [
                {
                    "id": msg.id,
                    "direction": msg.direction.value,
                    "message_text": msg.message_text,
                    "toon_format": f"{'U' if msg.direction.value == 'in' else 'B'}:{msg.message_text}",
                    "user_id": msg.telegram_user_id,  # Generic user_id (can be web session or telegram)
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "ai_response_used": msg.ai_response_used
                }
                for msg in messages
            ],
            "messages_toon": "|".join([
                f"{'U' if msg.direction.value == 'in' else 'B'}:{msg.message_text.replace('|', '‖')}"
                for msg in reversed(messages)
            ]),
            "activities": [
                {
                    "id": act.id,
                    "action_type": act.action_type,
                    "details": act.details if act.details else {},
                    "details_toon": ActivityService.details_to_toon(act.details) if act.details else "",
                    "timestamp": act.timestamp.isoformat() if act.timestamp else None
                }
                for act in activities
            ],
            "summary": {
                "total_messages": len(messages),
                "inbound_messages": len([m for m in messages if m.direction.value == "in"]),
                "outbound_messages": len([m for m in messages if m.direction.value == "out"]),
                "total_activities": len(activities),
                "has_name": bool(lead.name and lead.name not in ['User', 'Test User']),
                "has_phone": bool(lead.phone and not lead.phone.startswith('web_chat_') and not lead.phone.startswith('whatsapp_')),
                "has_location": bool(lead.lead_metadata and lead.lead_metadata.get('location')),
                "has_budget": bool(lead.lead_metadata and lead.lead_metadata.get('budget')),
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying lead data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

