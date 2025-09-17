from fastapi import Request
import time
import logging

logger = logging.getLogger(__name__)

async def security_logging_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response_time = time.time() - start_time
    
    client_ip = request.client.host
    method = request.method
    path = request.url.path
    
    logger.info(f"Request: {method} {path} - IP: {client_ip} - Status: {response.status_code} - Time: {response_time:.3f}s")
    return response
