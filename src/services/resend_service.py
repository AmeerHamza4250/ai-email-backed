"""
Resend email sending service.
"""
import resend
import asyncio
from typing import Optional, Dict, Any
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize Resend
if not settings.RESEND_API_KEY:
    logger.warning("RESEND_API_KEY is not set. Email sending will fail.")
else:
    resend.api_key = settings.RESEND_API_KEY


class ResendService:
    """Service for sending emails via Resend."""
    
    def __init__(self):
        # Use configured email or default - but warn if using default
        if hasattr(settings, 'RESEND_FROM_EMAIL') and settings.RESEND_FROM_EMAIL:
            self.from_email = settings.RESEND_FROM_EMAIL
        else:
            self.from_email = "onboarding@resend.dev"
            logger.warning(
                "RESEND_FROM_EMAIL not configured. Using default 'onboarding@resend.dev'. "
                "This will only work for testing emails to your own address. "
                "Set RESEND_FROM_EMAIL to an email from your verified domain."
            )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> dict:
        """
        Send an email via Resend.
        
        Returns:
            Response dict with email_id and status
        """
        if not settings.RESEND_API_KEY:
            raise Exception("RESEND_API_KEY is not configured. Please set it in your environment variables.")
        
        try:
            params = {
                "from": from_email or self.from_email,
                "to": to_email,
                "subject": subject,
                "html": html_body,
                # Enable open and click tracking (default: True, but explicit is better)
                "track_opens": True,
                "track_clicks": True,
            }
            
            if reply_to:
                params["reply_to"] = reply_to
            
            logger.info(f"Attempting to send email to {to_email}", from_email=params["from"], subject=subject)
            
            # Run the synchronous Resend call in an executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: resend.Emails.send(params))
            
            # Log the full response for debugging
            logger.info(f"Resend API response", response=response, to_email=to_email)
            
            # Handle different response formats
            email_id = None
            if isinstance(response, dict):
                email_id = response.get("id") or response.get("email_id")
            elif hasattr(response, "id"):
                email_id = response.id
            
            if not email_id:
                logger.warning(f"No email ID in Resend response", response=response)
                # Still return success if response exists (Resend might return differently)
                if response:
                    return {
                        "id": None,
                        "status": "sent",
                        "response": response
                    }
                else:
                    raise Exception("No response from Resend API")
            
            logger.info(f"Email sent successfully to {to_email}", email_id=email_id)
            
            return {
                "id": email_id,
                "email_id": email_id,  # Support both formats
                "status": "sent",
                "response": response
            }
            
        except Exception as e:
            error_msg = str(e)
            # Check for domain verification errors
            if "testing emails" in error_msg.lower() or "verify a domain" in error_msg.lower():
                logger.error(
                    f"Domain verification error: {error_msg}. "
                    f"Make sure RESEND_FROM_EMAIL is set to an email from your verified domain."
                )
                raise Exception(
                    f"Domain verification required: {error_msg}. "
                    f"Please set RESEND_FROM_EMAIL environment variable to an email address "
                    f"from your verified domain (e.g., 'noreply@yourdomain.com')."
                )
            logger.exception(f"Error sending email to {to_email}", exc_info=e)
            raise Exception(f"Failed to send email: {str(e)}")
    
    def convert_text_to_html(self, text: str) -> str:
        """Convert plain text to HTML."""
        # Simple conversion - replace newlines with <br>
        html = text.replace("\n", "<br>")
        return f"<html><body>{html}</body></html>"
    
    # Domain Management Methods
    async def create_domain(self, domain_name: str) -> Dict[str, Any]:
        """
        Create a new domain in Resend.
        
        Args:
            domain_name: The domain name to create (e.g., "example.com")
        
        Returns:
            Domain information dict
        """
        if not settings.RESEND_API_KEY:
            raise Exception("RESEND_API_KEY is not configured.")
        
        try:
            params: resend.Domains.CreateParams = {
                "name": domain_name,
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: resend.Domains.create(params))
            
            logger.info(f"Domain created: {domain_name}", response=response)
            return response if isinstance(response, dict) else {"domain": str(response)}
            
        except Exception as e:
            logger.exception(f"Error creating domain {domain_name}", exc_info=e)
            raise Exception(f"Failed to create domain: {str(e)}")
    
    async def get_domain(self, domain_id: str) -> Dict[str, Any]:
        """
        Get domain information by ID.
        
        Args:
            domain_id: The domain ID
        
        Returns:
            Domain information dict
        """
        if not settings.RESEND_API_KEY:
            raise Exception("RESEND_API_KEY is not configured.")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: resend.Domains.get(domain_id=domain_id))
            
            logger.info(f"Domain retrieved: {domain_id}", response=response)
            return response if isinstance(response, dict) else {"domain": str(response)}
            
        except Exception as e:
            logger.exception(f"Error getting domain {domain_id}", exc_info=e)
            raise Exception(f"Failed to get domain: {str(e)}")
    
    async def verify_domain(self, domain_id: str) -> Dict[str, Any]:
        """
        Verify a domain in Resend.
        
        Args:
            domain_id: The domain ID to verify
        
        Returns:
            Verification response dict
        """
        if not settings.RESEND_API_KEY:
            raise Exception("RESEND_API_KEY is not configured.")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: resend.Domains.verify(domain_id=domain_id))
            
            logger.info(f"Domain verification initiated: {domain_id}", response=response)
            return response if isinstance(response, dict) else {"verification": str(response)}
            
        except Exception as e:
            logger.exception(f"Error verifying domain {domain_id}", exc_info=e)
            raise Exception(f"Failed to verify domain: {str(e)}")

