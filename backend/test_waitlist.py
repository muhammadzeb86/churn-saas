#!/usr/bin/env python3
"""
Test script for the waitlist endpoint
"""
import asyncio
import httpx
import json

async def test_waitlist_endpoint():
    """Test the waitlist endpoint with various scenarios"""
    
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:8000"
        
        # Test 1: Valid email with source
        print("Test 1: Valid email with source")
        payload = {
            "email": "user@example.com",
            "source": "landing_page"
        }
        
        try:
            response = await client.post(
                f"{base_url}/api/waitlist",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test 2: Valid email without source (should use default)
        print("Test 2: Valid email without source")
        payload = {
            "email": "another@example.com"
        }
        
        try:
            response = await client.post(
                f"{base_url}/api/waitlist",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test 3: Invalid email format
        print("Test 3: Invalid email format")
        payload = {
            "email": "invalid-email",
            "source": "landing_page"
        }
        
        try:
            response = await client.post(
                f"{base_url}/api/waitlist",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test 4: Duplicate email (should return success)
        print("Test 4: Duplicate email")
        payload = {
            "email": "user@example.com",
            "source": "landing_page"
        }
        
        try:
            response = await client.post(
                f"{base_url}/api/waitlist",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_waitlist_endpoint()) 
