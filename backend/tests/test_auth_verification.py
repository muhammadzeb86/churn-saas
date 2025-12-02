"""
JWT Signature Verification Tests - Highway-Grade Coverage
===========================================================

This test suite provides comprehensive coverage for JWT authentication,
including JWKS client, signature verification, and middleware integration.

Test Coverage:
- JWKS Client: Caching, fetch, errors, graceful degradation
- JWT Verification: Valid, invalid, expired, tampered tokens
- Middleware: Auth flow, error handling, dev mode

Run with: pytest backend/tests/test_auth_verification.py -v --cov=backend/auth
Target Coverage: >95%

Author: RetainWise Backend Team
Last Updated: 2025-12-02
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi import HTTPException
from jose import jwt as jose_jwt, jwk
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError

# Import modules to test
from backend.auth.jwt_verifier import ProductionJWTVerifier, get_jwt_verifier, JWTVerificationError
from backend.auth.middleware import (
    get_current_user,
    _authenticate_dev_mode,
    _authenticate_production_verified,
    require_user_ownership
)


# ========================================================================
# TEST FIXTURES
# ========================================================================

@pytest.fixture
def valid_jwks_response():
    """
    Mock JWKS response from Clerk with valid RSA key.
    
    This represents what Clerk returns from /.well-known/jwks.json
    """
    return {
        "keys": [
            {
                "kid": "ins_2abc123",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtV",
                "e": "AQAB"
            },
            {
                "kid": "ins_2xyz789",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "xjlCRBqkQRaXdwVfJKhbWjeKpKlqkRqXdwVfJKhbWjeKpKlqkRqXdwVfJK",
                "e": "AQAB"
            }
        ]
    }


@pytest.fixture
def valid_jwt_payload():
    """Valid JWT payload matching Clerk's structure."""
    current_time = int(time.time())
    return {
        "sub": "user_2NNEqL2nrIRdJ194ndJqAHwEfxC",
        "email": "test@example.com",
        "email_verified": True,
        "name": "Test User",
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://img.clerk.com/test.jpg",
        "iss": "https://clerk.retainwiseanalytics.com",
        "iat": current_time,
        "exp": current_time + 3600,
        "nbf": current_time
    }


@pytest.fixture
def mock_http_response():
    """Mock httpx response for JWKS fetch."""
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = AsyncMock()
    return mock_resp


# ========================================================================
# JWKS CLIENT TESTS
# ========================================================================

class TestProductionJWTVerifier:
    """Test suite for ProductionJWTVerifier class."""
    
    def test_initialization_success(self):
        """Test verifier initializes with valid CLERK_FRONTEND_API."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            assert verifier.clerk_domain == 'clerk.example.com'
            assert verifier.jwks_url == 'https://clerk.example.com/.well-known/jwks.json'
            assert verifier.issuer == 'https://clerk.example.com'
            assert verifier.cache_ttl == 86400  # 24 hours
    
    def test_initialization_missing_env_var(self):
        """Test verifier raises error when CLERK_FRONTEND_API not set."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="CLERK_FRONTEND_API environment variable required"):
                ProductionJWTVerifier()
    
    def test_initialization_rejects_url_format(self):
        """Test verifier rejects full URLs (expects domain only)."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'https://clerk.example.com'}):
            with pytest.raises(ValueError, match="should be domain only"):
                ProductionJWTVerifier()
    
    @pytest.mark.asyncio
    async def test_get_jwks_fresh_cache(self, valid_jwks_response):
        """Test JWKS returns cached value when cache is fresh."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Populate cache
            verifier.jwks_cache = valid_jwks_response
            verifier.jwks_last_fetched = time.time()
            
            # Should return cache without fetch
            with patch('httpx.AsyncClient') as mock_client:
                result = await verifier.get_jwks()
                
                assert result == valid_jwks_response
                mock_client.assert_not_called()  # No fetch happened
    
    @pytest.mark.asyncio
    async def test_get_jwks_fetch_success(self, valid_jwks_response):
        """Test JWKS fetches from Clerk when cache empty."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Create properly async mock response
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=valid_jwks_response)
            mock_response.raise_for_status = AsyncMock()  # Make this async too
            mock_response.status_code = 200
            
            # Create async client mock
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                result = await verifier.get_jwks()
                
                assert result == valid_jwks_response
                assert verifier.jwks_cache == valid_jwks_response
                assert verifier.jwks_last_fetched > 0
    
    @pytest.mark.asyncio
    async def test_get_jwks_stale_cache_fallback(self, valid_jwks_response):
        """Test JWKS uses stale cache when fetch fails."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Set stale cache
            verifier.jwks_cache = valid_jwks_response
            verifier.jwks_last_fetched = time.time() - 90000  # 25 hours ago (stale)
            
            # Mock fetch failure
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                # Should return stale cache instead of failing
                result = await verifier.get_jwks()
                assert result == valid_jwks_response
    
    @pytest.mark.asyncio
    async def test_get_jwks_no_cache_fetch_fails(self):
        """Test JWKS raises 503 when fetch fails and no cache available."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # No cache, fetch fails
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                with pytest.raises(HTTPException) as exc_info:
                    await verifier.get_jwks()
                
                assert exc_info.value.status_code == 503
                assert "temporarily unavailable" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_get_jwks_invalid_structure(self):
        """Test JWKS handles invalid response structure."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Mock response with missing 'keys' field
            mock_http_response = AsyncMock()
            mock_http_response.json = AsyncMock(return_value={"invalid": "structure"})
            mock_http_response.raise_for_status = AsyncMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_http_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                with pytest.raises(HTTPException) as exc_info:
                    await verifier.get_jwks()
                
                assert exc_info.value.status_code == 503
    
    def test_find_signing_key_success(self, valid_jwks_response):
        """Test finding signing key by kid."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            key = verifier._find_signing_key(valid_jwks_response, "ins_2abc123")
            
            assert key['kid'] == 'ins_2abc123'
            assert key['kty'] == 'RSA'
    
    def test_find_signing_key_not_found(self, valid_jwks_response):
        """Test error when signing key not found in JWKS."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            with pytest.raises(JWTVerificationError, match="Signing key not found"):
                verifier._find_signing_key(valid_jwks_response, "unknown_kid")


# ========================================================================
# JWT VERIFICATION TESTS
# ========================================================================

class TestJWTVerification:
    """Test suite for JWT token verification logic."""
    
    @pytest.mark.asyncio
    async def test_verify_token_missing_kid(self):
        """Test rejection of token without kid in header."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Mock token with no kid
            with patch('jose.jwt.get_unverified_header', return_value={"alg": "RS256"}):
                with pytest.raises(JWTVerificationError, match="missing 'kid'"):
                    await verifier.verify_token("fake.jwt.token")
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid_structure(self):
        """Test rejection of malformed token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Token with wrong number of parts
            with pytest.raises(JWTVerificationError, match="Token structure invalid"):
                await verifier.verify_token("invalid.token")
    
    @pytest.mark.asyncio
    async def test_verify_token_too_short(self):
        """Test rejection of suspiciously short token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            with pytest.raises(JWTVerificationError, match="too short"):
                await verifier.verify_token("abc")
    
    @pytest.mark.asyncio
    async def test_verify_token_expired(self, valid_jwks_response):
        """Test rejection of expired token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            verifier.jwks_cache = valid_jwks_response
            verifier.jwks_last_fetched = time.time()
            
            with patch('jose.jwt.get_unverified_header', return_value={"kid": "ins_2abc123"}):
                with patch('jose.jwt.decode', side_effect=ExpiredSignatureError("Token expired")):
                    with pytest.raises(JWTVerificationError, match="expired"):
                        await verifier.verify_token("fake.jwt.token")
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid_claims(self, valid_jwks_response):
        """Test rejection of token with invalid claims."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            verifier.jwks_cache = valid_jwks_response
            verifier.jwks_last_fetched = time.time()
            
            with patch('jose.jwt.get_unverified_header', return_value={"kid": "ins_2abc123"}):
                with patch('jose.jwt.decode', side_effect=JWTClaimsError("Invalid issuer")):
                    with pytest.raises(JWTVerificationError, match="claims invalid"):
                        await verifier.verify_token("fake.jwt.token")
    
    @pytest.mark.asyncio
    async def test_verify_token_missing_sub_claim(self, valid_jwks_response):
        """Test rejection of token without 'sub' (user ID) claim."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            verifier.jwks_cache = valid_jwks_response
            verifier.jwks_last_fetched = time.time()
            
            # Payload without 'sub'
            payload_no_sub = {
                "email": "test@example.com",
                "iss": "https://clerk.example.com",
                "exp": time.time() + 3600
            }
            
            with patch('jose.jwt.get_unverified_header', return_value={"kid": "ins_2abc123"}):
                with patch('jose.jwk.construct', return_value=Mock()):
                    with patch('jose.jwt.decode', return_value=payload_no_sub):
                        with pytest.raises(JWTVerificationError, match="missing 'sub'"):
                            await verifier.verify_token("fake.jwt.token")
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, valid_jwks_response, valid_jwt_payload):
        """Test successful token verification (happy path)."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            verifier.jwks_cache = valid_jwks_response
            verifier.jwks_last_fetched = time.time()
            
            with patch('jose.jwt.get_unverified_header', return_value={"kid": "ins_2abc123"}):
                with patch('jose.jwk.construct', return_value=Mock()):
                    with patch('jose.jwt.decode', return_value=valid_jwt_payload):
                        result = await verifier.verify_token("valid.jwt.token")
                        
                        assert result['sub'] == 'user_2NNEqL2nrIRdJ194ndJqAHwEfxC'
                        assert result['email'] == 'test@example.com'


# ========================================================================
# MIDDLEWARE TESTS
# ========================================================================

class TestAuthenticationMiddleware:
    """Test suite for authentication middleware functions."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self):
        """Test rejection when credentials missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_authenticate_dev_mode_valid_token(self):
        """Test dev mode authentication with valid structure."""
        token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9."
        
        with patch.dict('os.environ', {'AUTH_DEV_MODE': 'true', 'ENVIRONMENT': 'test'}):
            # Mock PyJWT decode (patch where it's used, not the module)
            mock_payload = {
                "sub": "user_123",
                "email": "test@example.com",
                "email_verified": True,
                "name": "Test User",
                "given_name": "Test",
                "family_name": "User"
            }
            
            with patch('backend.auth.middleware.pyjwt.decode', return_value=mock_payload):
                result = await _authenticate_dev_mode(token)
                
                assert result['id'] == 'user_123'
                assert result['dev_mode'] is True
                assert result['email'] == 'test@example.com'
    
    @pytest.mark.asyncio
    async def test_authenticate_dev_mode_missing_sub(self):
        """Test dev mode rejects token without 'sub' claim."""
        with patch.dict('os.environ', {'AUTH_DEV_MODE': 'true', 'ENVIRONMENT': 'test'}):
            mock_payload = {"email": "test@example.com"}  # No 'sub'
            
            with patch('backend.auth.middleware.pyjwt.decode', return_value=mock_payload):
                with pytest.raises(HTTPException) as exc_info:
                    await _authenticate_dev_mode("fake.token")
                
                assert exc_info.value.status_code == 401
                assert "missing user ID" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_authenticate_production_verified_success(self, valid_jwt_payload):
        """Test production authentication with valid token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com', 'ENVIRONMENT': 'test'}):
            # Mock verifier
            mock_verifier = AsyncMock()
            mock_verifier.verify_token = AsyncMock(return_value=valid_jwt_payload)
            
            # Patch in jwt_verifier module where get_jwt_verifier actually lives
            with patch('backend.auth.jwt_verifier.get_jwt_verifier', return_value=mock_verifier):
                result = await _authenticate_production_verified("valid.token")
                
                assert result['id'] == 'user_2NNEqL2nrIRdJ194ndJqAHwEfxC'
                assert result['signature_verified'] is True
                assert result['dev_mode'] is False
                assert result['email'] == 'test@example.com'
    
    @pytest.mark.asyncio
    async def test_authenticate_production_verified_invalid_token(self):
        """Test production authentication with invalid token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com', 'ENVIRONMENT': 'test'}):
            # Mock verifier that raises error
            mock_verifier = AsyncMock()
            mock_verifier.verify_token = AsyncMock(
                side_effect=JWTVerificationError("Invalid signature")
            )
            
            with patch('backend.auth.jwt_verifier.get_jwt_verifier', return_value=mock_verifier):
                with pytest.raises(HTTPException) as exc_info:
                    await _authenticate_production_verified("invalid.token")
                
                assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_authenticate_production_import_error(self):
        """Test graceful handling when jwt_verifier module unavailable."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com', 'ENVIRONMENT': 'test'}):
            # Mock import failure
            with patch('backend.auth.jwt_verifier.get_jwt_verifier', side_effect=ImportError("Module not found")):
                with pytest.raises(HTTPException) as exc_info:
                    await _authenticate_production_verified("token")
                
                assert exc_info.value.status_code == 500
                assert "configuration error" in str(exc_info.value.detail).lower()
    
    def test_require_user_ownership_success(self):
        """Test authorization passes when user owns resource."""
        current_user = {"id": "user_123"}
        resource_user_id = "user_123"
        
        # Should not raise exception
        require_user_ownership(resource_user_id, current_user)
    
    def test_require_user_ownership_forbidden(self):
        """Test authorization fails when user doesn't own resource."""
        current_user = {"id": "user_123"}
        resource_user_id = "user_456"
        
        with pytest.raises(HTTPException) as exc_info:
            require_user_ownership(resource_user_id, current_user)
        
        assert exc_info.value.status_code == 403
        assert "permission" in str(exc_info.value.detail).lower()


# ========================================================================
# SINGLETON PATTERN TESTS
# ========================================================================

class TestJWTVerifierSingleton:
    """Test singleton pattern for JWT verifier."""
    
    @pytest.mark.asyncio
    async def test_get_jwt_verifier_singleton(self):
        """Test that get_jwt_verifier returns same instance."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            # Get verifier twice
            verifier1 = await get_jwt_verifier()
            verifier2 = await get_jwt_verifier()
            
            # Should be same instance
            assert verifier1 is verifier2
    
    @pytest.mark.asyncio
    async def test_get_jwt_verifier_thread_safe(self):
        """Test concurrent initialization doesn't create multiple instances."""
        import asyncio
        
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            # Reset singleton
            import backend.auth.jwt_verifier as jwt_verifier_module
            jwt_verifier_module._verifier = None
            
            # Create multiple concurrent requests
            async def get_verifier():
                return await get_jwt_verifier()
            
            results = await asyncio.gather(*[get_verifier() for _ in range(10)])
            
            # All should be same instance
            assert all(v is results[0] for v in results)


# ========================================================================
# INTEGRATION TESTS
# ========================================================================

class TestEndToEndAuthentication:
    """End-to-end integration tests simulating real requests."""
    
    @pytest.mark.asyncio
    async def test_full_auth_flow_dev_mode(self):
        """Test complete authentication flow in dev mode."""
        with patch.dict('os.environ', {'AUTH_DEV_MODE': 'true', 'ENVIRONMENT': 'test'}):
            from fastapi.security import HTTPAuthorizationCredentials
            
            mock_payload = {
                "sub": "user_dev_123",
                "email": "dev@example.com"
            }
            
            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "dev.token.here"
            
            with patch('backend.auth.middleware.pyjwt.decode', return_value=mock_payload):
                result = await get_current_user(credentials)
                
                assert result['id'] == 'user_dev_123'
                assert result['dev_mode'] is True
    
    @pytest.mark.asyncio
    async def test_full_auth_flow_production(self, valid_jwt_payload):
        """Test complete authentication flow in production mode."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com', 'AUTH_DEV_MODE': 'false', 'ENVIRONMENT': 'test'}):
            from fastapi.security import HTTPAuthorizationCredentials
            
            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "prod.jwt.token"
            
            # Mock verifier
            mock_verifier = AsyncMock()
            mock_verifier.verify_token = AsyncMock(return_value=valid_jwt_payload)
            
            with patch('backend.auth.jwt_verifier.get_jwt_verifier', return_value=mock_verifier):
                result = await get_current_user(credentials)
                
                assert result['id'] == 'user_2NNEqL2nrIRdJ194ndJqAHwEfxC'
                assert result['signature_verified'] is True
                assert result['dev_mode'] is False


# ========================================================================
# EDGE CASES & ERROR HANDLING
# ========================================================================

class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.mark.asyncio
    async def test_empty_token(self):
        """Test handling of empty token string."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            with pytest.raises(JWTVerificationError):
                await verifier.verify_token("")
    
    @pytest.mark.asyncio
    async def test_none_token(self):
        """Test handling of None token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            with pytest.raises(JWTVerificationError):
                await verifier.verify_token(None)
    
    @pytest.mark.asyncio
    async def test_whitespace_token(self):
        """Test handling of whitespace-only token."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            with pytest.raises(JWTVerificationError):
                await verifier.verify_token("   ")
    
    @pytest.mark.asyncio
    async def test_jwks_validation_missing_keys(self):
        """Test JWKS validation when 'keys' array is missing."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Mock response without 'keys'
            mock_http_response = AsyncMock()
            mock_http_response.json = AsyncMock(return_value={})
            mock_http_response.raise_for_status = AsyncMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_http_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                with pytest.raises(HTTPException):
                    await verifier.get_jwks()
    
    @pytest.mark.asyncio
    async def test_jwks_validation_empty_keys_array(self):
        """Test JWKS validation when 'keys' array is empty."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Mock response with empty keys
            mock_http_response = AsyncMock()
            mock_http_response.json = AsyncMock(return_value={"keys": []})
            mock_http_response.raise_for_status = AsyncMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_http_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                with pytest.raises(HTTPException):
                    await verifier.get_jwks()


# ========================================================================
# PERFORMANCE TESTS
# ========================================================================

class TestPerformance:
    """Test performance characteristics of JWT verification."""
    
    @pytest.mark.asyncio
    async def test_cache_prevents_multiple_fetches(self, valid_jwks_response):
        """Test that cache prevents redundant JWKS fetches."""
        with patch.dict('os.environ', {'CLERK_FRONTEND_API': 'clerk.example.com'}):
            verifier = ProductionJWTVerifier()
            
            # Track fetch count
            fetch_count = [0]  # Use list to avoid nonlocal issues
            
            async def mock_get(*args, **kwargs):
                fetch_count[0] += 1
                mock_resp = AsyncMock()
                mock_resp.json = AsyncMock(return_value=valid_jwks_response)
                mock_resp.raise_for_status = AsyncMock()
                mock_resp.status_code = 200
                return mock_resp
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get = mock_get
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client_instance):
                # Fetch 5 times
                for _ in range(5):
                    await verifier.get_jwks()
                
                # Should only fetch once (rest from cache)
                assert fetch_count[0] == 1


# ========================================================================
# TEST CONFIGURATION
# ========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=backend.auth", "--cov-report=term-missing"])

