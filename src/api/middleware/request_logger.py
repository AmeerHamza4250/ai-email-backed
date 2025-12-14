"""
Request logging middleware to log all API requests.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

# Use standard logging for request logs (simpler and more reliable)
logger = logging.getLogger("uvicorn.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests."""
    
    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()
        
        # Log request (simple format)
        client_host = request.client.host if request.client else "unknown"
        print(f"=> {request.method} {request.url.path} from {client_host}")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            print(f"<= {request.method} {request.url.path} {response.status_code} ({round(duration * 1000, 2)}ms)")
            
            return response
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            print(f"!! {request.method} {request.url.path} ERROR: {str(e)} ({round(duration * 1000, 2)}ms)")
            raise

