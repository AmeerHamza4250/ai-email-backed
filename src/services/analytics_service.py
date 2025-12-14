"""
Analytics service for calculating dashboard statistics.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import selectinload
from uuid import UUID
from src.models.user import User
from src.models.campaign import Campaign
from src.models.lead import Lead
from src.models.campaign_lead import CampaignLead
from src.models.email_event import EmailEvent, EmailEventType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Service for analytics calculations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_stats(self, user_id: UUID) -> dict:
        """Get dashboard statistics for a user."""
        try:
            # Count campaigns
            campaigns_stmt = select(func.count(Campaign.id)).where(
                Campaign.user_id == user_id
            )
            campaigns_result = await self.db.execute(campaigns_stmt)
            total_campaigns = campaigns_result.scalar() or 0
            
            # Count leads
            leads_stmt = select(func.count(Lead.id)).where(
                Lead.user_id == user_id
            )
            leads_result = await self.db.execute(leads_stmt)
            total_leads = leads_result.scalar() or 0
            
            # Count sent emails (campaign_leads with sent_at)
            sent_stmt = select(func.count(CampaignLead.id)).join(
                Campaign
            ).where(
                and_(
                    Campaign.user_id == user_id,
                    CampaignLead.sent_at.isnot(None)
                )
            )
            sent_result = await self.db.execute(sent_stmt)
            total_sent = sent_result.scalar() or 0
            
            # Count delivered emails (email events with DELIVERED type)
            delivered_stmt = select(func.count(EmailEvent.id)).join(
                CampaignLead
            ).join(Campaign).where(
                and_(
                    Campaign.user_id == user_id,
                    EmailEvent.event_type == EmailEventType.DELIVERED
                )
            )
            delivered_result = await self.db.execute(delivered_stmt)
            total_delivered = delivered_result.scalar() or 0
            
            # Count opened emails
            opened_stmt = select(func.count(EmailEvent.id)).join(
                CampaignLead
            ).join(Campaign).where(
                and_(
                    Campaign.user_id == user_id,
                    EmailEvent.event_type == EmailEventType.OPENED
                )
            )
            opened_result = await self.db.execute(opened_stmt)
            total_opened = opened_result.scalar() or 0
            
            # Count clicked emails
            clicked_stmt = select(func.count(EmailEvent.id)).join(
                CampaignLead
            ).join(Campaign).where(
                and_(
                    Campaign.user_id == user_id,
                    EmailEvent.event_type == EmailEventType.CLICKED
                )
            )
            clicked_result = await self.db.execute(clicked_stmt)
            total_clicked = clicked_result.scalar() or 0
            
            # Count replied emails (from CampaignLead.replied flag)
            # Note: If column doesn't exist, this will return 0
            try:
                replied_stmt = select(func.count(CampaignLead.id)).join(
                    Campaign
                ).where(
                    and_(
                        Campaign.user_id == user_id,
                        CampaignLead.replied == True
                    )
                )
                replied_result = await self.db.execute(replied_stmt)
                total_replied = replied_result.scalar() or 0
            except Exception as e:
                # Column might not exist in database yet - return 0
                logger.warning("replied column not found in campaign_leads table", error=str(e))
                total_replied = 0
            
            # Calculate rates
            open_rate = (total_opened / total_delivered) if total_delivered > 0 else 0.0
            click_rate = (total_clicked / total_delivered) if total_delivered > 0 else 0.0
            reply_rate = (total_replied / total_delivered) if total_delivered > 0 else 0.0
            
            return {
                "total_campaigns": total_campaigns,
                "total_leads": total_leads,
                "total_sent": total_sent,
                "total_delivered": total_delivered,
                "open_rate": round(open_rate, 4),
                "click_rate": round(click_rate, 4),
                "reply_rate": round(reply_rate, 4),
            }
            
        except Exception as e:
            logger.exception("Error calculating dashboard stats", exc_info=e)
            # Return zeros on error
            return {
                "total_campaigns": 0,
                "total_leads": 0,
                "total_sent": 0,
                "total_delivered": 0,
                "open_rate": 0.0,
                "click_rate": 0.0,
                "reply_rate": 0.0,
            }
    
    async def get_campaign_stats(self, user_id: UUID, campaign_id: UUID) -> dict:
        """Get statistics for a specific campaign."""
        try:
            # Verify campaign belongs to user
            campaign_stmt = select(Campaign).where(
                and_(
                    Campaign.id == campaign_id,
                    Campaign.user_id == user_id
                )
            )
            campaign_result = await self.db.execute(campaign_stmt)
            campaign = campaign_result.scalar_one_or_none()
            
            if not campaign:
                raise ValueError("Campaign not found")
            
            # Optimize: Use a single query with conditional aggregation for email events
            # This is much faster than multiple separate queries
            
            # Count sent emails (campaign_leads with sent_at)
            sent_stmt = select(func.count(CampaignLead.id)).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    CampaignLead.sent_at.isnot(None)
                )
            )
            
            # Count email events by type in a single query using conditional aggregation
            event_counts_stmt = select(
                func.sum(case((EmailEvent.event_type == EmailEventType.DELIVERED, 1), else_=0)).label("delivered"),
                func.sum(case((EmailEvent.event_type == EmailEventType.OPENED, 1), else_=0)).label("opened"),
                func.sum(case((EmailEvent.event_type == EmailEventType.CLICKED, 1), else_=0)).label("clicked"),
                func.sum(case((EmailEvent.event_type == EmailEventType.BOUNCED, 1), else_=0)).label("bounced"),
            ).select_from(
                EmailEvent
            ).join(
                CampaignLead, EmailEvent.campaign_lead_id == CampaignLead.id
            ).where(
                CampaignLead.campaign_id == campaign_id
            )
            
            # Count replied emails (from CampaignLead.replied flag)
            replied_stmt = select(func.count(CampaignLead.id)).where(
                and_(
                    CampaignLead.campaign_id == campaign_id,
                    CampaignLead.replied == True
                )
            )
            
            # Execute all queries
            sent_result = await self.db.execute(sent_stmt)
            total_sent = sent_result.scalar() or 0
            
            event_result = await self.db.execute(event_counts_stmt)
            event_row = event_result.first()
            if event_row:
                total_delivered = event_row.delivered or 0
                total_opened = event_row.opened or 0
                total_clicked = event_row.clicked or 0
                total_bounced = event_row.bounced or 0
            else:
                total_delivered = total_opened = total_clicked = total_bounced = 0
            
            # Try to get replied count (may fail if column doesn't exist)
            try:
                replied_result = await self.db.execute(replied_stmt)
                total_replied = replied_result.scalar() or 0
            except Exception as e:
                logger.warning("replied column not found in campaign_leads table", error=str(e))
                total_replied = 0
            
            return {
                "sent": total_sent,
                "delivered": total_delivered,
                "opened": total_opened,
                "clicked": total_clicked,
                "replied": total_replied,
                "bounced": total_bounced,
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.exception("Error calculating campaign stats", exc_info=e)
            # Return zeros on error
            return {
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "replied": 0,
                "bounced": 0,
            }

