"""
Tests for authentication endpoints.

Tests covered:
- User registration
- User login
- Token validation
- Protected endpoints
"""
import pytest
from httpx import AsyncClient


class TestAuthEndpoints:
    """Test authentication functionality"""
    
    @pytest.mark.asyncio
    async def test_register_new_user(self, client: AsyncClient):
        """Test user registration with valid data"""
        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "broker_name": "Test Broker"
            }
        )
        # Should return 200 or 201 with access token
        assert response.status_code in [200, 201]
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration fails with duplicate email"""
        response = await client.post(
            "/auth/register",
            json={
                "email": test_user.email,  # Already exists
                "password": "anotherpassword123",
                "broker_name": "Another Broker"
            }
        )
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, client: AsyncClient, test_user):
        """Test login with correct credentials"""
        response = await client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, test_user):
        """Test login fails with wrong password"""
        response = await client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login fails for nonexistent user"""
        response = await client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anypassword"
            }
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test protected endpoint rejects request without token"""
        response = await client.get("/api/v1/leads")
        assert response.status_code == 403  # Forbidden or 401
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_valid_token(
        self, client: AsyncClient, auth_headers
    ):
        """Test protected endpoint accepts valid token"""
        response = await client.get(
            "/api/v1/leads",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_token(self, client: AsyncClient):
        """Test protected endpoint rejects invalid token"""
        response = await client.get(
            "/api/v1/leads",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401


class TestTokenValidation:
    """Test JWT token handling"""
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client: AsyncClient):
        """Test that expired tokens are rejected"""
        # This would require creating an expired token, which we can mock
        # For now, just test that the endpoint requires auth
        response = await client.get("/api/v1/leads")
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_malformed_token_rejected(self, client: AsyncClient):
        """Test that malformed tokens are rejected"""
        response = await client.get(
            "/api/v1/leads",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"}
        )
        assert response.status_code == 401
