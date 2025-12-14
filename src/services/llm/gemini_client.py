"""
Gemini LLM client for email generation.
"""
import google.generativeai as genai
from typing import Optional
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

# Use gemini-2.0-flash-exp model (latest as of 2025)
MODEL_NAME = "gemini-2.5-flash"


class GeminiClient:
    """Client for interacting with Gemini API."""
    
    def __init__(self):
        self.model = genai.GenerativeModel(MODEL_NAME)
    
    async def generate_email(
        self,
        lead_name: str,
        lead_company: Optional[str],
        email_template: Optional[str] = None,
        additional_context: Optional[dict] = None,
        campaign_description: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Generate personalized email content using Gemini.
        
        Args:
            lead_name: Lead's name
            lead_company: Lead's company (optional)
            email_template: Additional instructions (optional)
            additional_context: Additional context from lead data
            campaign_description: Description of what's being sold/promoted
            
        Returns:
            Tuple of (subject, body)
        """
        try:
            # Build prompt
            prompt = self._build_prompt(
                lead_name=lead_name,
                lead_company=lead_company,
                email_template=email_template,
                additional_context=additional_context,
                campaign_description=campaign_description
            )
            
            # Generate content
            response = self.model.generate_content(prompt)
            
            # Parse response (assuming format: SUBJECT: ...\n\nBODY: ...)
            content = response.text
            
            # Extract subject and body
            subject, body = self._parse_response(content)
            
            logger.info(f"Generated email for {lead_name}")
            
            return subject, body
            
        except Exception as e:
            logger.exception(f"Error generating email for {lead_name}", exc_info=e)
            raise Exception(f"Failed to generate email: {str(e)}")
    
    def _build_prompt(
        self,
        lead_name: str,
        lead_company: Optional[str],
        email_template: Optional[str],
        additional_context: Optional[dict],
        campaign_description: Optional[str] = None
    ) -> str:
        """Build the prompt for Gemini."""
        prompt_parts = [
            "You are an expert email outreach specialist. Generate a personalized, professional B2B sales email.",
            "",
            "LEAD INFORMATION:",
            f"- Name: {lead_name}",
        ]
        
        if lead_company:
            prompt_parts.append(f"- Company: {lead_company}")
        
        if additional_context:
            prompt_parts.append(f"- Additional Context: {additional_context}")
        
        prompt_parts.extend([
            "",
            "WHAT YOU'RE SELLING/PROMOTING:",
        ])
        
        if campaign_description:
            prompt_parts.append(campaign_description)
        else:
            prompt_parts.append("(No product/service description provided)")
        
        prompt_parts.extend([
            "",
            "EMAIL REQUIREMENTS:",
            "- Professional and friendly tone",
            "- Highly personalized to the lead's name and company",
            "- Reference their company/industry when relevant",
            "- Clear value proposition based on what you're selling",
            "- Specific benefits that would interest this lead",
            "- Strong call-to-action",
            "- Keep it concise (150-200 words)",
            "- No generic templates - make it feel personal",
            "",
        ])
        
        if email_template:
            prompt_parts.extend([
                "ADDITIONAL INSTRUCTIONS:",
                email_template,
                "",
            ])
        
        prompt_parts.extend([
            "Generate the email in this exact format:",
            "SUBJECT: [compelling subject line that's personalized]",
            "",
            "BODY:",
            "[personalized email body that connects the product/service to this specific lead]",
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_response(self, content: str) -> tuple[str, str]:
        """Parse Gemini response to extract subject and body."""
        lines = content.split("\n")
        
        subject = ""
        body_lines = []
        in_body = False
        
        for line in lines:
            if line.startswith("SUBJECT:"):
                subject = line.replace("SUBJECT:", "").strip()
            elif line.startswith("BODY:") or in_body:
                if line.startswith("BODY:"):
                    in_body = True
                else:
                    body_lines.append(line)
        
        body = "\n".join(body_lines).strip()
        
        # Fallback if parsing fails
        if not subject:
            subject = "Re: Business Opportunity"
        if not body:
            body = content
        
        return subject, body

