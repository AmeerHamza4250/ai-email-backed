"""
Common API response schemas.
"""
from pydantic import BaseModel
from typing import Optional, Any, List


class ApiResponse(BaseModel):
    """Standard API response format."""
    status: str  # "success" or "error"
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response format."""
    status: str = "error"
    message: str
    errors: Optional[List[str]] = None

