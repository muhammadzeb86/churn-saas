from fastapi import Request, HTTPException, status
import logging

logger = logging.getLogger(__name__)

async def input_validation_middleware(request, call_next):
    # Basic validation - check for obvious SQL injection attempts
    for key, value in request.query_params.items():
        if isinstance(value, str) and any(keyword in value.upper() for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP"]):
            logger.warning(f"Potential SQL injection attempt in {key}: {value[:100]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid input detected"
            )
    
    response = await call_next(request)
    return response
