"""
Automated tests for the RetainWise backend API
"""
import os
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Set up test environment before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["S3_BUCKET"] = "test-bucket"
os.environ["PREDICTIONS_QUEUE_URL"] = ""

from backend.main import app
from backend.core.config import settings
from backend.api.database import init_db

# Test configuration
TEST_USER_ID = "test-user-123"
TEST_EMAIL = "test@example.com"

# Removed session-scoped event_loop fixture - using pytest-asyncio defaults
# This prevents conflicts with function-scoped async fixtures

@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)

@pytest.fixture
async def async_client():
    """Create async test client"""
    # Initialize database for each test
    await init_db()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

class TestAPI:
    """Test suite for API endpoints"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "RetainWise Analytics backend is running" in response.json()["message"]
    
    def test_health_check(self, client):
        """Test basic health check"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "retainwise-backend"
    
    def test_monitoring_health(self, client):
        """Test monitoring health endpoint"""
        response = client.get("/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        # Basic monitoring health returns simple status
        assert data["status"] == "healthy"
        assert data["service"] == "retainwise-backend"
    
    def test_monitoring_metrics(self, client):
        """Test monitoring metrics endpoint"""
        response = client.get("/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "error_rate" in data
        assert "uptime_seconds" in data
    
    def test_monitoring_status(self, client):
        """Test monitoring status endpoint"""
        response = client.get("/monitoring/status")
        assert response.status_code == 200
        data = response.json()
        # Status can be "starting", "operational", "warning", or "degraded"
        assert data["status"] in ["starting", "operational", "warning", "degraded"]
        assert "error_rate" in data
        assert "uptime" in data
    
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
        assert "message" in data
    
    @pytest.mark.asyncio
    async def test_waitlist_invalid_email(self, async_client):
        """Test waitlist with invalid email"""
        payload = {
            "email": "invalid-email",
            "source": "test"
        }
        response = await async_client.post("/api/waitlist", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "Invalid email format" in data["error"]
    
    @pytest.mark.asyncio
    async def test_predictions_unauthorized(self, async_client):
        """Test predictions endpoint without authentication"""
        response = await async_client.get("/predictions")
        # Should return 422 for missing query parameters or 401 for auth
        assert response.status_code in [401, 403, 422]
    
    @pytest.mark.asyncio
    async def test_uploads_unauthorized(self, async_client):
        """Test uploads endpoint without authentication"""
        response = await async_client.get("/uploads")
        # Should return 422 for missing query parameters or 401 for auth
        assert response.status_code in [401, 403, 422]

class TestConfiguration:
    """Test configuration and environment setup"""
    
    def test_environment_variables(self):
        """Test that environment variables are set correctly"""
        assert os.environ.get("ENVIRONMENT") == "test"
        assert "sqlite" in os.environ.get("DATABASE_URL", "").lower()
        assert os.environ.get("AWS_REGION") == "us-east-1"
    
    def test_sql_logging_configuration(self):
        """Test SQL logging is properly configured"""
        import logging
        # In test environment, SQL logging should be enabled
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
        
        # All requests should succeed for health endpoint (reasonable rate limit)
        assert all(status == 200 for status in responses)
    
    def test_input_validation(self, client):
        """Test input validation middleware"""
        # Test with potential SQL injection in query parameter
        malicious_input = "test'; DROP TABLE users; --"
        
        # Test input validation - should block malicious input
        response = client.get("/health", params={"test_param": malicious_input})
        
        # The input validation middleware should catch this and return 400
        assert response.status_code == 400
        
        # Test with clean input - should work fine
        response = client.get("/health", params={"test_param": "clean_input"})
        assert response.status_code == 200

# Test runner configuration
if __name__ == "__main__":
    # Set test environment
    os.environ["ENVIRONMENT"] = "test"
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])

# Configure test environment before importing app
def pytest_configure():
    """Configure pytest environment"""
    import os
    # Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["S3_BUCKET"] = "test-bucket"
    os.environ["PREDICTIONS_QUEUE_URL"] = ""
