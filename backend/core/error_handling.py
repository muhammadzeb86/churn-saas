"""
Production Error Handling & Retry Logic for RetainWise

Implements:
1. User-friendly error codes & messages
2. Exponential backoff retry logic
3. Circuit breaker pattern
4. Graceful degradation

Goal: Turn technical errors into actionable user guidance

Author: RetainWise Engineering
Date: December 15, 2025
Version: 1.0
"""

import asyncio
import random
import time
import hashlib
from typing import TypeVar, Callable, Optional, Any, Dict
from functools import wraps
from enum import Enum

from fastapi import HTTPException, status
from backend.core.observability import production_logger, cloudwatch_metrics

# ========================================
# ERROR CODES & MESSAGES
# ========================================

class ErrorCode(str, Enum):
    """
    Standardized error codes for user-friendly messaging
    
    Format: ERR-{Category}-{Number}
    
    Categories:
    -----------
    - 1xxx: User errors (client-side, user can fix)
    - 2xxx: Security errors (authentication, authorization)
    - 3xxx: System errors (server-side, we need to fix)
    - 4xxx: External service errors (AWS, third-party)
    
    Why Error Codes?
    ----------------
    1. Debugging: Search logs for "ERR-1001" instantly
    2. Support: User reports "ERR-3002", support knows exact issue
    3. Monitoring: Track error distribution in CloudWatch
    4. Documentation: Each code has solution article
    """
    
    # ========================================
    # 1xxx: USER ERRORS
    # ========================================
    
    # File upload errors
    FILE_TOO_LARGE = "ERR-1001"
    INVALID_FILE_TYPE = "ERR-1002"
    TOO_MANY_ROWS = "ERR-1003"
    INVALID_CSV_FORMAT = "ERR-1004"
    CSV_INJECTION_DETECTED = "ERR-1005"
    
    # Data validation errors
    MISSING_REQUIRED_COLUMNS = "ERR-1101"
    INVALID_DATA_FORMAT = "ERR-1102"
    DUPLICATE_CUSTOMER_IDS = "ERR-1103"
    
    # Request errors
    INVALID_REQUEST_PAYLOAD = "ERR-1201"
    MISSING_REQUIRED_FIELD = "ERR-1202"
    
    # ========================================
    # 2xxx: SECURITY ERRORS
    # ========================================
    
    # Authentication
    INVALID_TOKEN = "ERR-2001"
    TOKEN_EXPIRED = "ERR-2002"
    MISSING_TOKEN = "ERR-2003"
    
    # Authorization
    ACCESS_DENIED = "ERR-2101"
    RESOURCE_NOT_FOUND = "ERR-2102"
    INSUFFICIENT_PERMISSIONS = "ERR-2103"
    
    # Rate limiting
    RATE_LIMIT_EXCEEDED = "ERR-2201"
    
    # ========================================
    # 3xxx: SYSTEM ERRORS
    # ========================================
    
    # Prediction service
    PREDICTION_FAILED = "ERR-3001"
    ML_MODEL_ERROR = "ERR-3002"
    DATA_PROCESSING_ERROR = "ERR-3003"
    
    # Database
    DATABASE_CONNECTION_FAILED = "ERR-3101"
    DATABASE_QUERY_FAILED = "ERR-3102"
    DATABASE_TIMEOUT = "ERR-3103"
    
    # Internal
    INTERNAL_SERVER_ERROR = "ERR-3201"
    UNEXPECTED_ERROR = "ERR-3202"
    
    # ========================================
    # 4xxx: EXTERNAL SERVICE ERRORS
    # ========================================
    
    # S3
    S3_UPLOAD_FAILED = "ERR-4001"
    S3_DOWNLOAD_FAILED = "ERR-4002"
    S3_ACCESS_DENIED = "ERR-4003"
    
    # SQS
    SQS_SEND_FAILED = "ERR-4101"
    SQS_RECEIVE_FAILED = "ERR-4102"
    
    # Clerk (Authentication)
    CLERK_API_ERROR = "ERR-4201"


class ErrorResponse:
    """
    User-friendly error response builder
    
    Before (Bad UX):
    ----------------
    {
      "detail": "KeyError: 'customerID'"
    }
    # User: "What does this mean?!"
    
    After (Good UX):
    ----------------
    {
      "error": {
        "code": "ERR-1101",
        "message": "Your CSV is missing the 'customerID' column.",
        "suggestion": "Please add a column named 'customerID' with unique customer identifiers.",
        "docs_url": "https://docs.retainwise.ai/errors/ERR-1101",
        "reference_id": "a3b2c1d4"
      }
    }
    # User: Clear action to take!
    """
    
    # Error code definitions
    MESSAGES = {
        # File upload errors
        ErrorCode.FILE_TOO_LARGE: {
            "message": "Your file is too large.",
            "suggestion": "Please upload a file smaller than 50MB. You can split large files into multiple uploads.",
            "docs_url": "https://docs.retainwise.ai/errors/file-too-large"
        },
        ErrorCode.INVALID_FILE_TYPE: {
            "message": "Invalid file type.",
            "suggestion": "Please upload a CSV file. Other formats (Excel, JSON) are not supported yet.",
            "docs_url": "https://docs.retainwise.ai/errors/invalid-file-type"
        },
        ErrorCode.TOO_MANY_ROWS: {
            "message": "Your file has too many rows.",
            "suggestion": "Please upload files with maximum 10,000 rows. You can split larger datasets into multiple files.",
            "docs_url": "https://docs.retainwise.ai/errors/too-many-rows"
        },
        ErrorCode.INVALID_CSV_FORMAT: {
            "message": "Your file is not a valid CSV.",
            "suggestion": "Please ensure your file is saved as CSV format. Check for corrupted data or special characters.",
            "docs_url": "https://docs.retainwise.ai/errors/invalid-csv"
        },
        
        # Data validation errors
        ErrorCode.MISSING_REQUIRED_COLUMNS: {
            "message": "Your CSV is missing required columns.",
            "suggestion": "Please include these columns: customerID, and at least 3 behavioral metrics (e.g., total_spend, usage_frequency).",
            "docs_url": "https://docs.retainwise.ai/csv-format"
        },
        
        # Security errors
        ErrorCode.ACCESS_DENIED: {
            "message": "You don't have permission to access this resource.",
            "suggestion": "This prediction belongs to another user. Please check your prediction history.",
            "docs_url": "https://docs.retainwise.ai/errors/access-denied"
        },
        ErrorCode.RATE_LIMIT_EXCEEDED: {
            "message": "You've exceeded the rate limit.",
            "suggestion": "Please wait 60 seconds before trying again. Consider upgrading for higher limits.",
            "docs_url": "https://docs.retainwise.ai/pricing"
        },
        
        # System errors
        ErrorCode.PREDICTION_FAILED: {
            "message": "Prediction processing failed.",
            "suggestion": "Our team has been notified. Please try again in a few minutes. If the issue persists, contact support.",
            "docs_url": "https://docs.retainwise.ai/support"
        },
        ErrorCode.DATABASE_CONNECTION_FAILED: {
            "message": "Database connection failed.",
            "suggestion": "We're experiencing temporary issues. Please try again in a few minutes.",
            "docs_url": "https://status.retainwise.ai"
        },
        
        # S3 errors
        ErrorCode.S3_UPLOAD_FAILED: {
            "message": "File upload failed.",
            "suggestion": "Please check your internet connection and try again. If the issue persists, contact support.",
            "docs_url": "https://docs.retainwise.ai/support"
        },
    }
    
    @classmethod
    def build(
        cls,
        error_code: ErrorCode,
        technical_details: str = "",
        custom_message: Optional[str] = None,
        custom_suggestion: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build user-friendly error response
        
        Args:
        -----
        error_code: Standard error code
        technical_details: Technical error message (logged, not shown to user)
        custom_message: Override default message
        custom_suggestion: Override default suggestion
        
        Returns:
        --------
        {
          "error": {
            "code": "ERR-xxxx",
            "message": "User-friendly message",
            "suggestion": "Actionable next steps",
            "docs_url": "https://...",
            "reference_id": "abc123"  # For support
          }
        }
        """
        error_def = cls.MESSAGES.get(
            error_code,
            {
                "message": "An unexpected error occurred.",
                "suggestion": "Please try again. If the issue persists, contact support.",
                "docs_url": "https://docs.retainwise.ai/support"
            }
        )
        
        # Generate reference ID for support
        reference_id = hashlib.sha256(
            f"{error_code}{technical_details}{time.time()}".encode()
        ).hexdigest()[:8]
        
        # Log technical details
        production_logger.logger.error(
            "user_facing_error",
            error_code=error_code,
            technical_details=technical_details,
            reference_id=reference_id,
            severity="ERROR"
        )
        
        # Record error metric
        cloudwatch_metrics.record_error(
            error_type=error_code,
            operation="api_request"
        )
        
        return {
            "error": {
                "code": error_code,
                "message": custom_message or error_def["message"],
                "suggestion": custom_suggestion or error_def["suggestion"],
                "docs_url": error_def["docs_url"],
                "reference_id": reference_id
            }
        }


# ========================================
# RETRY LOGIC WITH EXPONENTIAL BACKOFF
# ========================================

T = TypeVar('T')

class RetryStrategy:
    """
    Exponential backoff retry strategy
    
    Why Retry?
    ----------
    Transient failures happen:
    - Network timeout (1% of requests)
    - Database connection pool exhausted (temporary)
    - S3 throttling (retry = success)
    
    Without Retries:
    ----------------
    1% failure rate = 10 failed predictions per 1000
    = Angry customers
    
    With Retries (3 attempts):
    --------------------------
    Effective failure rate = 1% * 1% * 1% = 0.0001% = 1 per million
    = Happy customers
    
    Exponential Backoff:
    --------------------
    Attempt 1: Wait 1 second
    Attempt 2: Wait 2 seconds
    Attempt 3: Wait 4 seconds
    Attempt 4: Wait 8 seconds
    
    Why Exponential?
    ----------------
    - Linear backoff (1s, 2s, 3s, 4s): Hammers overloaded service
    - Exponential (1s, 2s, 4s, 8s): Gives service time to recover
    
    Jitter:
    -------
    Add random ±10% to avoid thundering herd problem
    (1000 clients all retry at exact same time = DDoS yourself)
    """
    
    @staticmethod
    def calculate_delay(
        attempt: int,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True
    ) -> float:
        """
        Calculate retry delay with exponential backoff + jitter
        
        Args:
        -----
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        jitter: Add random ±10% to prevent thundering herd
        
        Returns:
        --------
        Delay in seconds
        
        Example:
        --------
        attempt=0: 1.0s  ± jitter
        attempt=1: 2.0s  ± jitter
        attempt=2: 4.0s  ± jitter
        attempt=3: 8.0s  ± jitter
        attempt=4: 16.0s ± jitter
        attempt=5: 30.0s (max_delay cap)
        """
        delay = min(base_delay * (2 ** attempt), max_delay)
        
        if jitter:
            # Add ±10% jitter
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)  # Never negative
    
    @classmethod
    def retry(
        cls,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exceptions: tuple = (Exception,),
        on_retry: Optional[Callable] = None
    ):
        """
        Decorator for automatic retry with exponential backoff
        
        Usage:
        ------
        @RetryStrategy.retry(
            max_retries=3,
            base_delay=1.0,
            exceptions=(S3UploadError, DatabaseConnectionError)
        )
        async def upload_to_s3(file_data):
            # This will retry 3 times if S3UploadError occurs
            return await s3.upload(file_data)
        
        Args:
        -----
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exceptions: Tuple of exceptions to retry on
        on_retry: Callback function(attempt, exception, delay)
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    
                    except exceptions as e:
                        last_exception = e
                        
                        # Don't retry on last attempt
                        if attempt == max_retries:
                            break
                        
                        # Calculate delay
                        delay = cls.calculate_delay(
                            attempt=attempt,
                            base_delay=base_delay,
                            max_delay=max_delay,
                            jitter=True
                        )
                        
                        # Log retry
                        production_logger.logger.warning(
                            "retrying_operation",
                            operation=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay_seconds=delay,
                            error_type=type(e).__name__,
                            error_message=str(e),
                            severity="WARNING"
                        )
                        
                        # Call on_retry callback if provided
                        if on_retry:
                            on_retry(attempt, e, delay)
                        
                        # Wait before retry
                        await asyncio.sleep(delay)
                
                # All retries exhausted
                production_logger.logger.error(
                    "retry_exhausted",
                    operation=func.__name__,
                    max_retries=max_retries,
                    error_type=type(last_exception).__name__,
                    error_message=str(last_exception),
                    severity="ERROR"
                )
                
                raise last_exception
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                """Synchronous version of retry wrapper"""
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt == max_retries:
                            break
                        
                        delay = cls.calculate_delay(
                            attempt=attempt,
                            base_delay=base_delay,
                            max_delay=max_delay,
                            jitter=True
                        )
                        
                        production_logger.logger.warning(
                            "retrying_operation",
                            operation=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay_seconds=delay,
                            error_type=type(e).__name__,
                            severity="WARNING"
                        )
                        
                        if on_retry:
                            on_retry(attempt, e, delay)
                        
                        time.sleep(delay)
                
                production_logger.logger.error(
                    "retry_exhausted",
                    operation=func.__name__,
                    max_retries=max_retries,
                    error_type=type(last_exception).__name__,
                    severity="ERROR"
                )
                
                raise last_exception
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator


# ========================================
# CIRCUIT BREAKER PATTERN
# ========================================

class CircuitBreaker:
    """
    Circuit breaker pattern for graceful degradation
    
    Problem:
    --------
    External service (e.g., S3) is down.
    Without circuit breaker:
    - Every request waits 30s for timeout
    - All requests fail slowly
    - User experience = terrible
    
    With circuit breaker:
    --------
    After 5 consecutive failures:
    - Open circuit (fail fast, don't even try)
    - Return cached data or degraded response
    - Check every 30s if service recovered
    - Close circuit when service back
    
    States:
    -------
    CLOSED: Normal operation, requests pass through
    OPEN: Service down, fail fast (return cached/degraded)
    HALF_OPEN: Testing if service recovered
    
    Example:
    --------
    breaker = CircuitBreaker(
        failure_threshold=5,
        timeout_seconds=30
    )
    
    @breaker.call
    async def call_external_api():
        # If circuit OPEN, raises CircuitBreakerOpen immediately
        # If circuit CLOSED, executes normally
        return await external_api.call()
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.half_open_call_count = 0
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == "OPEN":
            # Check if timeout expired (transition to HALF_OPEN)
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.timeout_seconds:
                    production_logger.logger.info(
                        "circuit_breaker_half_open",
                        timeout_seconds=self.timeout_seconds,
                        severity="INFO"
                    )
                    self.state = "HALF_OPEN"
                    self.half_open_call_count = 0
                    return False
            return True
        return False
    
    def record_success(self):
        """Record successful call"""
        if self.state == "HALF_OPEN":
            self.half_open_call_count += 1
            
            # If enough successful calls, close circuit
            if self.half_open_call_count >= self.half_open_max_calls:
                production_logger.logger.info(
                    "circuit_breaker_closed",
                    previous_failures=self.failure_count,
                    severity="INFO"
                )
                self.state = "CLOSED"
                self.failure_count = 0
        
        # Reset failure count on success
        self.failure_count = 0
    
    def record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        # Open circuit if threshold exceeded
        if self.failure_count >= self.failure_threshold and self.state == "CLOSED":
            production_logger.logger.error(
                "circuit_breaker_opened",
                failure_threshold=self.failure_threshold,
                timeout_seconds=self.timeout_seconds,
                severity="ERROR"
            )
            self.state = "OPEN"
    
    def call(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to wrap function with circuit breaker
        
        Usage:
        ------
        breaker = CircuitBreaker()
        
        @breaker.call
        async def risky_operation():
            # Protected by circuit breaker
            pass
        """
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Check if circuit is open
            if self.is_open():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=ErrorResponse.build(
                        error_code=ErrorCode.PREDICTION_FAILED,
                        technical_details="Circuit breaker is OPEN"
                    )
                )
            
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            
            except Exception as e:
                self.record_failure()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            if self.is_open():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=ErrorResponse.build(
                        error_code=ErrorCode.PREDICTION_FAILED,
                        technical_details="Circuit breaker is OPEN"
                    )
                )
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            
            except Exception as e:
                self.record_failure()
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


# ========================================
# SINGLETON INSTANCES
# ========================================

# Circuit breakers for external services
s3_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=30.0
)

database_circuit_breaker = CircuitBreaker(
    failure_threshold=10,
    timeout_seconds=60.0
)

# ========================================
# MODULE INFO
# ========================================

__all__ = [
    'ErrorCode',
    'ErrorResponse',
    'RetryStrategy',
    'CircuitBreaker',
    's3_circuit_breaker',
    'database_circuit_breaker'
]

