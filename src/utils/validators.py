"""
Validation utilities.
"""
from email_validator import validate_email, EmailNotValidError
from typing import Optional


def validate_email_address(email: str) -> tuple[bool, Optional[str]]:
    """
    Validate an email address.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        validate_email(email, check_deliverability=False)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string value.
    
    Args:
        value: String to sanitize
        max_length: Maximum length (truncate if longer)
        
    Returns:
        Sanitized string
    """
    if not value:
        return ""
    
    # Remove leading/trailing whitespace
    sanitized = value.strip()
    
    # Truncate if needed
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

