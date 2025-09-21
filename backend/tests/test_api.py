"""
Automated tests for the RetainWise backend API
"""
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings
import os

# Test configuration
TEST_USER_ID = "test-user-123"
TEST_EMAIL = "test@example.com"

class TestAPI:
    """Test suite for API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        """Create async test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "RetainWise Analytics backend is running" in response.json()["message"]
    
    def test_health_check(self, client):
        """Test basic health check"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "retainwise-backend"
    
    def test_monitoring_health(self, client):
        """Test monitoring health endpoint"""
        response = client.get("/monitoring/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_monitoring_metrics(self, client):
        """Test metrics endpoint"""
        response = client.get("/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "error_rate" in data
    
    def test_monitoring_status(self, client):
        """Test status endpoint"""
        response = client.get("/monitoring/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["operational", "warning", "degraded", "starting"]
    
    @pytest.mark.asyncio
    async def test_waitlist_valid_email(self, async_client):
        """Test waitlist with valid email"""
        payload = {
            "email": TEST_EMAIL,
            "source": "test"
        }
        response = await async_client.post("/api/waitlist", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_waitlist_invalid_email(self, async_client):
        """Test waitlist with invalid email"""
        payload = {
            "email": "invalid-email",
            "source": "test"
        }
        response = await async_client.post("/api/waitlist", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid email format" in data["error"]
    
    def test_predictions_unauthorized(self, client):
        """Test predictions endpoint without auth"""
        response = client.get(f"/predictions?user_id={TEST_USER_ID}")
        # Should require authentication
        assert response.status_code in [401, 403]
    
    def test_uploads_unauthorized(self, client):
        """Test uploads endpoint without auth"""
        response = client.get(f"/uploads?user_id={TEST_USER_ID}")
        # Should require authentication
        assert response.status_code in [401, 403]

class TestConfiguration:
    """Test configuration and settings"""
    
    def test_environment_variables(self):
        """Test that required environment variables are set"""
        # These should be set in test environment
        assert hasattr(settings, "ENVIRONMENT")
        assert hasattr(settings, "AWS_REGION")
        assert hasattr(settings, "S3_BUCKET")
    
    def test_sql_logging_configuration(self):
        """Test SQL logging configuration"""
        # Test that SQL logging is configured based on environment
        import logging
        sql_logger = logging.getLogger("sqlalchemy.engine")
        
        if settings.ENVIRONMENT == "production":
            assert sql_logger.level >= logging.WARNING
        else:
            assert sql_logger.level <= logging.INFO

class TestSecurity:
    """Test security features"""
    
    def test_rate_limiting(self, client):
        """Test rate limiting middleware"""
        # Make multiple rapid requests to test rate limiting
        responses = []
        for i in range(10):
            response = client.get("/health")
            responses.append(response.status_code)
        
        # All requests should succeed for health endpoint (low rate limit)
        assert all(status == 200 for status in responses)
    
    def test_input_validation(self, client):
        """Test input validation middleware"""
        # Test with potential SQL injection
        malicious_input = "'; DROP TABLE users; --"
        response = client.get(f"/predictions?user_id={malicious_input}")
        
        # Should be blocked by input validation
        assert response.status_code == 400

# Test runner configuration
if __name__ == "__main__":
    # Set test environment
    os.environ["ENVIRONMENT"] = "test"
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
