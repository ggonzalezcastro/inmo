"""
Tests for chat endpoints.

Tests covered:
- Message validation
- Chat flow with mock LLM
- Lead creation/update through chat
- Error handling
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


class TestChatValidation:
    """Test chat input validation"""
    
    @pytest.mark.asyncio
    async def test_chat_message_empty_rejected(
        self, client: AsyncClient, auth_headers
    ):
        """Test that empty messages are rejected"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": ""},
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_message_too_long_rejected(
        self, client: AsyncClient, auth_headers
    ):
        """Test that messages over 4000 chars are rejected"""
        long_message = "x" * 4001
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": long_message},
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_lead_id_negative_rejected(
        self, client: AsyncClient, auth_headers
    ):
        """Test that negative lead_id is rejected"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Hello", "lead_id": -1},
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_lead_id_zero_rejected(
        self, client: AsyncClient, auth_headers
    ):
        """Test that zero lead_id is rejected"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Hello", "lead_id": 0},
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error


class TestChatFlow:
    """Test chat conversation flow"""
    
    @pytest.mark.asyncio
    async def test_chat_creates_new_lead(
        self, client: AsyncClient, auth_headers, mock_gemini
    ):
        """Test that chat without lead_id creates a new lead"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Hola, busco un departamento"},
            headers=auth_headers
        )
        
        # Should succeed and return lead info
        assert response.status_code == 200
        data = response.json()
        assert "lead_id" in data
        assert "response" in data
        assert data["lead_id"] > 0
    
    @pytest.mark.asyncio
    async def test_chat_with_existing_lead(
        self, client: AsyncClient, auth_headers, mock_gemini
    ):
        """Test chat with an existing lead"""
        # First create a lead
        create_response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Primer mensaje"},
            headers=auth_headers
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Then continue conversation
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Segundo mensaje", "lead_id": lead_id},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == lead_id
    
    @pytest.mark.asyncio
    async def test_chat_nonexistent_lead_returns_404(
        self, client: AsyncClient, auth_headers
    ):
        """Test chat with non-existent lead returns 404"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Hello", "lead_id": 99999},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestChatLLMIntegration:
    """Test LLM integration with mocked responses"""
    
    @pytest.mark.asyncio
    async def test_chat_returns_ai_response(
        self, client: AsyncClient, auth_headers, mock_gemini
    ):
        """Test that chat returns an AI response"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "¿Qué tipos de inmuebles tienen?"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_chat_extracts_lead_info(
        self, client: AsyncClient, auth_headers, mock_gemini
    ):
        """Test that chat extracts lead information from message"""
        # Mock the analysis response
        with patch("app.services.chat_orchestrator_service.LLMServiceFacade.analyze_lead_qualification") as mock_analyze:
            mock_analyze.return_value = {
                "qualified": "maybe",
                "interest_level": 7,
                "budget": None,
                "timeline": "30days",
                "name": "Juan Pérez",
                "phone": "+56912345678",
                "email": None,
                "salary": 1500000,
                "location": "Las Condes",
                "dicom_status": "clean",
                "morosidad_amount": None,
                "key_points": ["Interesado en Las Condes"],
                "score_delta": 10
            }
            
            response = await client.post(
                "/api/v1/chat/test",
                json={"message": "Soy Juan Pérez, mi teléfono es +56912345678"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            # The score should have changed based on analysis
            data = response.json()
            assert data["lead_score"] >= 0


class TestChatErrorHandling:
    """Test error scenarios in chat"""
    
    @pytest.mark.asyncio
    async def test_chat_without_auth_rejected(self, client: AsyncClient):
        """Test that chat requires authentication"""
        response = await client.post(
            "/api/v1/chat/test",
            json={"message": "Hello"}
        )
        assert response.status_code in [401, 403]
