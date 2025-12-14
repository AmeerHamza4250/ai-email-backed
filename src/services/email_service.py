"""
Email generation and sending service.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from src.models.campaign import Campaign
from src.models.lead import Lead
from src.models.campaign_lead import CampaignLead
from src.models.email_event import EmailEvent, EmailEventType
from src.models.campaign import CampaignStatus
from src.services.llm.gemini_client import GeminiClient
from src.services.resend_service import ResendService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service for email generation and sending."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gemini_client = GeminiClient()
        self.resend_service = ResendService()
    
    async def generate_emails_for_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
        lead_ids: Optional[List[UUID]] = None
    ) -> tuple[int, int]:
        """
        Generate personalized emails for campaign leads.
        
        Returns:
            Tuple of (generated_count, failed_count)
        """
        # Get campaign
        stmt = select(Campaign).where(
            and_(Campaign.id == campaign_id, Campaign.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError("Campaign not found")
        
        # Update campaign status
        campaign.status = CampaignStatus.GENERATING
        await self.db.commit()
        
        # Get campaign leads
        if lead_ids:
            stmt = select(CampaignLead).join(Lead).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    CampaignLead.lead_id.in_(lead_ids),
                    Lead.user_id == user_id
                )
            )
        else:
            stmt = select(CampaignLead).join(Lead).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    Lead.user_id == user_id
                )
            )
        
        result = await self.db.execute(stmt)
        campaign_leads = result.scalars().all()
        
        generated = 0
        failed = 0
        
        # Generate emails for each lead
        for campaign_lead in campaign_leads:
            try:
                # Get lead details
                lead_stmt = select(Lead).where(Lead.id == campaign_lead.lead_id)
                lead_result = await self.db.execute(lead_stmt)
                lead = lead_result.scalar_one()
                
                # Generate email using campaign description as product/service info
                subject, body = await self.gemini_client.generate_email(
                    lead_name=lead.name,
                    lead_company=lead.company,
                    email_template=campaign.email_template,
                    additional_context=lead.additional_data,
                    campaign_description=campaign.description  # This is what they're selling
                )
                
                # Update campaign_lead
                campaign_lead.subject = subject
                campaign_lead.body = body
                
                generated += 1
                
            except Exception as e:
                failed += 1
                logger.error(f"Error generating email for lead {campaign_lead.lead_id}", error=str(e))
        
        # Update campaign status
        campaign.status = CampaignStatus.DRAFT
        await self.db.commit()
        
        return generated, failed
    
    async def send_emails_for_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
        campaign_lead_ids: Optional[List[UUID]] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Send emails for campaign leads via Resend.
        
        Returns:
            Tuple of (sent_count, failed_count, errors)
        """
        # Get campaign
        stmt = select(Campaign).where(
            and_(Campaign.id == campaign_id, Campaign.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise ValueError("Campaign not found")
        
        # Update campaign status
        campaign.status = CampaignStatus.SENDING
        await self.db.commit()
        
        # Get campaign leads
        if campaign_lead_ids:
            stmt = select(CampaignLead).join(Lead).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    CampaignLead.lead_id.in_(campaign_lead_ids),
                    Lead.user_id == user_id
                )
            )
        else:
            stmt = select(CampaignLead).join(Lead).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    Lead.user_id == user_id
                )
            )
        
        result = await self.db.execute(stmt)
        campaign_leads = result.scalars().all()
        
        sent = 0
        failed = 0
        errors = []
        
        # Send emails
        for campaign_lead in campaign_leads:
            try:
                # Check if email is generated
                if not campaign_lead.subject or not campaign_lead.body:
                    failed += 1
                    errors.append(f"Lead {campaign_lead.lead_id}: Email not generated")
                    continue
                
                # Get lead details
                lead_stmt = select(Lead).where(Lead.id == campaign_lead.lead_id)
                lead_result = await self.db.execute(lead_stmt)
                lead = lead_result.scalar_one()
                
                # Convert text to HTML
                html_body = self.resend_service.convert_text_to_html(campaign_lead.body)
                
                # Send email via Resend
                response = await self.resend_service.send_email(
                    to_email=lead.email,
                    subject=campaign_lead.subject,
                    html_body=html_body
                )
                
                # Update campaign_lead
                campaign_lead.sent = True
                campaign_lead.sent_at = datetime.utcnow()
                email_id = response.get("id") or response.get("email_id")
                if email_id:
                    campaign_lead.resend_message_id = email_id
                
                # Create sent event
                sent_event = EmailEvent(
                    campaign_lead_id=campaign_lead.id,
                    event_type=EmailEventType.SENT,
                    event_data={"email_id": email_id}
                )
                self.db.add(sent_event)
                
                sent += 1
                
            except Exception as e:
                failed += 1
                error_msg = f"Lead {campaign_lead.lead_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Error sending email for lead {campaign_lead.lead_id}", error=str(e))
        
        # Update campaign status
        if sent > 0:
            campaign.status = CampaignStatus.COMPLETED
            campaign.sent_at = datetime.utcnow()
        else:
            campaign.status = CampaignStatus.DRAFT
        
        await self.db.commit()
        
        return sent, failed, errors
    
    async def track_email_event(
        self,
        campaign_lead_id: UUID,
        event_type: EmailEventType,
        metadata: Optional[dict] = None
    ) -> EmailEvent:
        """Track an email event (open, click, reply, bounce)."""
        event = EmailEvent(
            campaign_lead_id=campaign_lead_id,
            event_type=event_type,
            event_data=metadata
        )
        
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        
        return event

