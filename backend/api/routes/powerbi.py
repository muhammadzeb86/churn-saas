from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any
import os
import requests
from datetime import datetime, timedelta
from backend.auth.middleware import get_current_user_dev_mode
from backend.models import User

router = APIRouter()

WORKSPACE_ID = os.getenv("POWERBI_WORKSPACE_ID")
REPORT_ID = os.getenv("POWERBI_REPORT_ID")
CLIENT_ID = os.getenv("POWERBI_CLIENT_ID")
CLIENT_SECRET = os.getenv("POWERBI_CLIENT_SECRET")
TENANT_ID = os.getenv("POWERBI_TENANT_ID")

@router.get("/embed-token", response_model=Dict[str, str])
async def get_embed_token(current_user: Dict[str, Any] = Depends(get_current_user_dev_mode)):
    """Generate a Power BI embed token for the report."""
    try:
        # Get Azure AD token
        token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        # Generate embed token
        embed_url = f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/reports/{REPORT_ID}"
        embed_token_url = f"https://api.powerbi.com/v1.0/myorg/GenerateToken"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        embed_token_request = {
            "reports": [{
                "id": REPORT_ID
            }],
            "identities": [{
                "username": "user@example.com",  # TODO: Use actual user email
                "roles": ["Reader"],
                "datasets": []
            }],
            "lifetimeInMinutes": 60
        }
        
        embed_token_response = requests.post(
            embed_token_url, 
            headers=headers,
            json=embed_token_request
        )
        embed_token_response.raise_for_status()
        
        return {
            "embedUrl": embed_url,
            "embedToken": embed_token_response.json()["token"],
            "reportId": REPORT_ID
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating Power BI embed token: {str(e)}"
        )
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing required environment variable: {str(e)}"
        ) 
