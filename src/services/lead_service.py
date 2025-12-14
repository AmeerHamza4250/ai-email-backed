"""
Lead service for managing leads.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Tuple
from uuid import UUID
from src.models.lead import Lead
from src.schemas.lead import LeadCreate, LeadResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LeadService:
    """Service for lead operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_lead(self, user_id: UUID, lead_data: LeadCreate) -> Lead:
        """Create a new lead."""
        # Check for duplicate email per user
        stmt = select(Lead).where(
            and_(Lead.user_id == user_id, Lead.email == lead_data.email)
        )
        result = await self.db.execute(stmt)
        existing_lead = result.scalar_one_or_none()
        
        if existing_lead:
            # Update existing lead
            existing_lead.name = lead_data.name
            existing_lead.company = lead_data.company
            existing_lead.email_id = lead_data.email_id
            existing_lead.email_subject = lead_data.email_subject
            existing_lead.email_type = lead_data.email_type
            existing_lead.sent_status = lead_data.sent_status
            existing_lead.reply_status = lead_data.reply_status
            existing_lead.time_to_reply_hours = lead_data.time_to_reply_hours
            existing_lead.additional_data = lead_data.additional_data
            await self.db.commit()
            await self.db.refresh(existing_lead)
            return existing_lead
        
        # Create new lead
        new_lead = Lead(
            user_id=user_id,
            name=lead_data.name,
            email=lead_data.email,
            company=lead_data.company,
            email_id=lead_data.email_id,
            email_subject=lead_data.email_subject,
            email_type=lead_data.email_type,
            sent_status=lead_data.sent_status,
            reply_status=lead_data.reply_status,
            time_to_reply_hours=lead_data.time_to_reply_hours,
            additional_data=lead_data.additional_data
        )
        
        self.db.add(new_lead)
        await self.db.commit()
        await self.db.refresh(new_lead)
        
        return new_lead
    
    async def create_leads_batch(
        self, 
        user_id: UUID, 
        leads_data: List[LeadCreate]
    ) -> Tuple[int, int, List[str]]:
        """
        Create multiple leads in batch (optimized for large imports).
        
        Returns:
            Tuple of (imported_count, failed_count, errors)
        """
        if not leads_data:
            return 0, 0, []
        
        imported = 0
        failed = 0
        errors = []
        
        # Get all existing emails for this user in one query
        existing_emails_stmt = select(Lead.email).where(Lead.user_id == user_id)
        existing_result = await self.db.execute(existing_emails_stmt)
        existing_emails = {email.lower() for email in existing_result.scalars().all()}
        
        # Batch size for commits
        BATCH_SIZE = 100
        leads_to_add = []
        leads_to_update = []
        
        # Separate new leads from updates
        for idx, lead_data in enumerate(leads_data, start=1):
            try:
                email_lower = lead_data.email.lower()
                if email_lower in existing_emails:
                    # Will update existing
                    leads_to_update.append((idx, lead_data))
                else:
                    # New lead
                    leads_to_add.append((idx, lead_data))
                    existing_emails.add(email_lower)  # Track to avoid duplicates in batch
            except Exception as e:
                failed += 1
                error_msg = f"Row {idx}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Error processing lead {idx}", error=str(e))
        
        # Process new leads in batches
        for batch_start in range(0, len(leads_to_add), BATCH_SIZE):
            batch = leads_to_add[batch_start:batch_start + BATCH_SIZE]
            try:
                for idx, lead_data in batch:
                    new_lead = Lead(
                        user_id=user_id,
                        name=lead_data.name,
                        email=lead_data.email,
                        company=lead_data.company,
                        email_id=lead_data.email_id,
                        email_subject=lead_data.email_subject,
                        email_type=lead_data.email_type,
                        sent_status=lead_data.sent_status,
                        reply_status=lead_data.reply_status,
                        time_to_reply_hours=lead_data.time_to_reply_hours,
                        additional_data=lead_data.additional_data
                    )
                    self.db.add(new_lead)
                
                await self.db.commit()
                imported += len(batch)
                logger.info(f"Imported batch of {len(batch)} leads", batch_start=batch_start)
            except Exception as e:
                await self.db.rollback()
                failed += len(batch)
                for idx, _ in batch:
                    errors.append(f"Row {idx}: {str(e)}")
                logger.error(f"Error importing batch starting at {batch_start}", error=str(e))
        
        # Process updates
        for idx, lead_data in leads_to_update:
            try:
                stmt = select(Lead).where(
                    and_(Lead.user_id == user_id, Lead.email == lead_data.email)
                )
                result = await self.db.execute(stmt)
                existing_lead = result.scalar_one_or_none()
                
                if existing_lead:
                    existing_lead.name = lead_data.name
                    existing_lead.company = lead_data.company
                    existing_lead.email_id = lead_data.email_id
                    existing_lead.email_subject = lead_data.email_subject
                    existing_lead.email_type = lead_data.email_type
                    existing_lead.sent_status = lead_data.sent_status
                    existing_lead.reply_status = lead_data.reply_status
                    existing_lead.time_to_reply_hours = lead_data.time_to_reply_hours
                    existing_lead.additional_data = lead_data.additional_data
                    imported += 1
            except Exception as e:
                failed += 1
                error_msg = f"Row {idx}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Error updating lead {idx}", error=str(e))
        
        # Commit any remaining updates
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("Error committing updates", error=str(e))
        
        logger.info(f"Batch import complete: {imported} imported, {failed} failed")
        return imported, failed, errors
    
    async def get_leads(
        self, 
        user_id: UUID, 
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[Lead], int]:
        """Get leads for a user with pagination."""
        # Count total
        count_stmt = select(Lead).where(Lead.user_id == user_id)
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())
        
        # Get paginated results
        stmt = select(Lead).where(
            Lead.user_id == user_id
        ).order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(stmt)
        leads = result.scalars().all()
        
        return list(leads), total
    
    async def get_lead_by_id(self, user_id: UUID, lead_id: UUID) -> Lead | None:
        """Get a lead by ID for a specific user."""
        stmt = select(Lead).where(
            and_(Lead.id == lead_id, Lead.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

