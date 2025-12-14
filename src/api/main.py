"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.utils.config import settings
from src.api.middleware.error_handler import (
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
)
from src.utils.logger import get_logger
from src.api.middleware.request_logger import RequestLoggingMiddleware

logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    debug=settings.DEBUG,
)

# Request logging middleware (should be first to log all requests)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware - Allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Email Outreach Automation System API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint to verify API is working."""
    return {"status": "success", "message": "API is working!", "timestamp": "2025-12-11"}


# Import and register routes
from src.api.routes import auth, analytics, leads, campaigns, emails, webhooks, ml

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(emails.router, prefix="/api/v1/emails", tags=["Emails"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(ml.router, prefix="/api/v1/ml", tags=["ML"])


if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    
    # Suppress reloader warnings on Windows
    if sys.platform == "win32":
        os.environ["PYTHONUNBUFFERED"] = "1"
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_dirs=["src"] if settings.DEBUG else None,
        reload_includes=["*.py"],
        log_level="info",
        access_log=True,
    )

