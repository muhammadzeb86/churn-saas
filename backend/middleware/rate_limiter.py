from fastapi import Request, HTTPException, status
import time
import asyncio
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_per_minute=60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(deque)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, client_ip):
        async with self.lock:
            now = time.time()
            minute_ago = now - 60
            
            while self.requests[client_ip] and self.requests[client_ip][0] < minute_ago:
                self.requests[client_ip].popleft()
            
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return False
            
            self.requests[client_ip].append(now)
            return True

rate_limiter = RateLimiter(requests_per_minute=60)

async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host
    
    if not await rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    response = await call_next(request)
    return response
