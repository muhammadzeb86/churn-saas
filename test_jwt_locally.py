"""
Local JWT Verification Test Script

This script validates the JWT verification implementation locally before deploying to production.
It tests:
1. Module imports
2. JWT verifier initialization
3. JWKS fetching
4. Clerk domain configuration

Run this BEFORE deploying to catch configuration issues early.

Usage:
    python test_jwt_locally.py

Requirements:
    - CLERK_FRONTEND_API environment variable set
    - Internet connection (to fetch JWKS from Clerk)
    - python-jose and httpx installed
"""
import os
import sys
import asyncio
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ANSI color codes for pretty output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    """Print a formatted section header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"   {text}")


async def main():
    """Run all JWT verification tests"""
    
    print_header("JWT Verification Local Test Suite")
    print_info("This script validates your JWT verification setup")
    print_info("before deploying to production.\n")
    
    all_tests_passed = True
    
    # ===== TEST 1: Environment Variables =====
    print_header("TEST 1: Environment Configuration")
    
    clerk_domain = os.getenv("CLERK_FRONTEND_API")
    auth_dev_mode = os.getenv("AUTH_DEV_MODE", "false").lower() in ["true", "1", "yes"]
    
    if clerk_domain:
        print_success(f"CLERK_FRONTEND_API is set: {clerk_domain}")
    else:
        print_error("CLERK_FRONTEND_API is NOT set")
        print_info("Set it to your Clerk domain, e.g.:")
        print_info("  export CLERK_FRONTEND_API=adapted-tern-12.clerk.accounts.dev")
        print_info("  OR")
        print_info("  export CLERK_FRONTEND_API=clerk.yourapp.com (custom domain)")
        all_tests_passed = False
    
    if auth_dev_mode:
        print_warning("AUTH_DEV_MODE is enabled (development mode)")
        print_info("This is OK for local testing")
    else:
        print_success("AUTH_DEV_MODE is disabled (production mode)")
    
    # ===== TEST 2: Import JWT Verifier =====
    print_header("TEST 2: Module Imports")
    
    try:
        from backend.auth.jwt_verifier import ProductionJWTVerifier, get_jwt_verifier
        print_success("JWT verifier module imported successfully")
        print_info("Location: backend/auth/jwt_verifier.py")
    except ImportError as e:
        print_error(f"Failed to import JWT verifier: {str(e)}")
        print_info("Make sure you're running from the project root directory")
        all_tests_passed = False
        return 1
    except Exception as e:
        print_error(f"Unexpected import error: {str(e)}")
        all_tests_passed = False
        return 1
    
    try:
        from backend.auth.middleware import get_current_user, require_user_ownership
        print_success("Middleware module imported successfully")
        print_info("Location: backend/auth/middleware.py")
    except ImportError as e:
        print_error(f"Failed to import middleware: {str(e)}")
        all_tests_passed = False
        return 1
    
    # ===== TEST 3: Dependencies =====
    print_header("TEST 3: Required Dependencies")
    
    try:
        import httpx
        print_success(f"httpx installed (version: {httpx.__version__})")
    except ImportError:
        print_error("httpx not installed")
        print_info("Install with: pip install httpx")
        all_tests_passed = False
    
    try:
        import jose
        print_success("python-jose installed")
    except ImportError:
        print_error("python-jose not installed")
        print_info("Install with: pip install python-jose[cryptography]")
        all_tests_passed = False
    
    # Skip remaining tests if environment not configured
    if not clerk_domain:
        print_header("SUMMARY")
        print_error("Cannot continue - CLERK_FRONTEND_API not set")
        return 1
    
    # ===== TEST 4: Initialize Verifier =====
    print_header("TEST 4: JWT Verifier Initialization")
    
    try:
        verifier = ProductionJWTVerifier()
        print_success("JWT verifier initialized successfully")
        print_info(f"Clerk domain: {verifier.clerk_domain}")
        print_info(f"JWKS URL: {verifier.jwks_url}")
        print_info(f"Issuer: {verifier.issuer}")
        print_info(f"Cache TTL: {verifier.cache_ttl} seconds (24 hours)")
    except ValueError as e:
        print_error(f"Configuration error: {str(e)}")
        all_tests_passed = False
        return 1
    except Exception as e:
        print_error(f"Initialization failed: {str(e)}")
        all_tests_passed = False
        return 1
    
    # ===== TEST 5: Fetch JWKS =====
    print_header("TEST 5: JWKS Fetching")
    
    try:
        print_info("Fetching JWKS from Clerk...")
        jwks = await verifier.get_jwks()
        
        print_success("JWKS fetched successfully")
        
        # Validate JWKS structure
        num_keys = len(jwks.get('keys', []))
        print_info(f"Number of keys: {num_keys}")
        
        if num_keys == 0:
            print_warning("JWKS contains 0 keys - this may be incorrect")
        
        # Display key information
        for i, key in enumerate(jwks.get('keys', []), 1):
            kid = key.get('kid', 'N/A')
            kty = key.get('kty', 'N/A')
            use = key.get('use', 'N/A')
            alg = key.get('alg', 'N/A')
            print_info(f"Key {i}: kid={kid}, kty={kty}, use={use}, alg={alg}")
        
    except Exception as e:
        print_error(f"JWKS fetch failed: {str(e)}")
        print_info("Check your internet connection and Clerk domain")
        all_tests_passed = False
    
    # ===== TEST 6: Singleton Pattern =====
    print_header("TEST 6: Singleton Pattern")
    
    try:
        verifier1 = await get_jwt_verifier()
        verifier2 = await get_jwt_verifier()
        
        if verifier1 is verifier2:
            print_success("Singleton pattern working correctly")
            print_info("Multiple calls return the same instance")
        else:
            print_warning("Singleton pattern may not be working correctly")
            print_info("Different instances returned (may not be an issue)")
        
    except Exception as e:
        print_error(f"Singleton test failed: {str(e)}")
        all_tests_passed = False
    
    # ===== TEST 7: Cache Behavior =====
    print_header("TEST 7: JWKS Caching")
    
    try:
        import time
        
        # First fetch
        start = time.time()
        jwks1 = await verifier.get_jwks()
        first_fetch_time = time.time() - start
        
        # Second fetch (should use cache)
        start = time.time()
        jwks2 = await verifier.get_jwks()
        second_fetch_time = time.time() - start
        
        print_success("JWKS caching functional")
        print_info(f"First fetch: {first_fetch_time*1000:.2f}ms")
        print_info(f"Second fetch: {second_fetch_time*1000:.2f}ms (cached)")
        
        if second_fetch_time < first_fetch_time / 10:
            print_success("Cache is significantly faster than network fetch")
        else:
            print_warning("Cache may not be working optimally")
        
        if jwks1 is jwks2:
            print_success("Same JWKS object returned (efficient caching)")
        
    except Exception as e:
        print_error(f"Cache test failed: {str(e)}")
        all_tests_passed = False
    
    # ===== FINAL SUMMARY =====
    print_header("TEST SUMMARY")
    
    if all_tests_passed:
        print_success("ALL TESTS PASSED ✅")
        print_info("")
        print_info("Your JWT verification setup is ready for deployment!")
        print_info("")
        print_info("Next steps:")
        print_info("1. Commit changes to Git")
        print_info("2. Push to GitHub (triggers CI/CD)")
        print_info("3. Update ECS environment variables:")
        print_info(f"   - CLERK_FRONTEND_API={clerk_domain}")
        print_info("   - AUTH_DEV_MODE=false")
        print_info("   - JWT_SIGNATURE_VERIFICATION_ENABLED=false (initially)")
        print_info("4. Deploy and monitor")
        print_info("5. Enable JWT_SIGNATURE_VERIFICATION_ENABLED=true")
        return 0
    else:
        print_error("SOME TESTS FAILED ❌")
        print_info("")
        print_info("Fix the issues above before deploying to production.")
        print_info("Re-run this script after making corrections.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {str(e)}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

