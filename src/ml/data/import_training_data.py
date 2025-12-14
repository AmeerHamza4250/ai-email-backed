"""
Script to import CSV training data into the database.

Usage:
    python -m src.ml.data.import_training_data \
        --csv "path/to/data.csv" \
        --user-id <uuid> \
        --campaign-name "ML Training Dataset"
"""
import asyncio
import argparse
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
from uuid import UUID
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_
from src.database.session import DATABASE_URL, async_engine
from src.models.user import User
from src.models.lead import Lead
from src.models.campaign import Campaign, CampaignStatus
from src.models.campaign_lead import CampaignLead
from src.utils.validators import validate_email_address
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def get_or_create_user(session: AsyncSession, user_id: UUID) -> User:
    """Get user by ID or raise error if not found."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"User with ID {user_id} not found. Please create a user first.")
    
    return user


async def get_or_create_lead(
    session: AsyncSession,
    user_id: UUID,
    name: str,
    email: str
) -> Lead:
    """Get existing lead or create new one."""
    # Check for existing lead
    stmt = select(Lead).where(
        and_(Lead.user_id == user_id, Lead.email == email.lower().strip())
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update name if different
        if existing.name != name:
            existing.name = name
            await session.commit()
            await session.refresh(existing)
        return existing
    
    # Create new lead
    new_lead = Lead(
        user_id=user_id,
        name=name.strip(),
        email=email.lower().strip(),
        company=None,
        additional_data=None
    )
    session.add(new_lead)
    await session.commit()
    await session.refresh(new_lead)
    return new_lead


async def create_training_campaign(
    session: AsyncSession,
    user_id: UUID,
    campaign_name: str
) -> Campaign:
    """Create a training campaign."""
    campaign = Campaign(
        user_id=user_id,
        name=campaign_name,
        description="Training dataset for ML model",
        email_template=None,
        status=CampaignStatus.COMPLETED,
        sent_at=datetime.now(timezone.utc)
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def import_csv_data(
    csv_path: str,
    user_id: UUID,
    campaign_name: str = "ML Training Dataset"
) -> Dict[str, Any]:
    """
    Import CSV training data into database.
    
    Args:
        csv_path: Path to CSV file
        user_id: User ID to associate data with
        campaign_name: Name for the training campaign
        
    Returns:
        Dictionary with import statistics
    """
    # Create async session
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        # Validate user exists
        user = await get_or_create_user(session, user_id)
        logger.info(f"Importing data for user: {user.email}")
        
        # Read CSV
        logger.info(f"Reading CSV from: {csv_path}")
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")
        
        # Validate required columns
        required_columns = [
            'Email_ID', 'Recipient_Name', 'Recipient_Email',
            'Email_Subject', 'Email_Type', 'Sent_Status', 'Reply_Status'
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        logger.info(f"Found {len(df)} rows in CSV")
        
        # Create training campaign
        campaign = await create_training_campaign(session, user_id, campaign_name)
        logger.info(f"Created campaign: {campaign.id}")
        
        # Statistics
        stats = {
            'total_rows': len(df),
            'imported_leads': 0,
            'imported_campaign_leads': 0,
            'failed_rows': 0,
            'errors': []
        }
        
        # Track unique leads by email
        leads_cache: Dict[str, Lead] = {}
        
        # Process each row
        for idx, row in df.iterrows():
            try:
                # Validate email
                email = str(row['Recipient_Email']).strip()
                is_valid, error = validate_email_address(email)
                if not is_valid:
                    stats['failed_rows'] += 1
                    stats['errors'].append(f"Row {idx + 2}: Invalid email '{email}': {error}")
                    continue
                
                # Get or create lead
                lead_key = email.lower()
                if lead_key not in leads_cache:
                    lead = await get_or_create_lead(
                        session,
                        user_id,
                        str(row['Recipient_Name']).strip(),
                        email
                    )
                    leads_cache[lead_key] = lead
                    stats['imported_leads'] += 1
                else:
                    lead = leads_cache[lead_key]
                
                # Prepare additional data
                additional_data = {
                    'email_type': str(row.get('Email_Type', '')),
                    'time_to_reply_hours': float(row['Time_to_Reply_Hours']) if pd.notna(row.get('Time_to_Reply_Hours')) else None,
                    'email_id': int(row['Email_ID']) if pd.notna(row.get('Email_ID')) else None
                }
                
                # Convert Sent_Status to boolean
                sent_status = str(row['Sent_Status']).strip().upper()
                is_sent = sent_status == 'SENT'
                
                # Reply_Status is already boolean
                replied = bool(row['Reply_Status']) if pd.notna(row['Reply_Status']) else False
                
                # Create CampaignLead
                campaign_lead = CampaignLead(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    subject=str(row['Email_Subject']).strip()[:500],  # Limit to 500 chars
                    body="",  # No body in CSV
                    sent=is_sent,
                    sent_at=datetime.now(timezone.utc) if is_sent else None,
                    opened=False,  # Not in CSV
                    clicked=False,  # Not in CSV
                    replied=replied,
                    bounced=(sent_status == 'FAILED'),
                    additional_data=additional_data if additional_data else None
                )
                
                session.add(campaign_lead)
                stats['imported_campaign_leads'] += 1
                
                # Commit in batches of 100
                if (idx + 1) % 100 == 0:
                    await session.commit()
                    logger.info(f"Processed {idx + 1} rows...")
                
            except Exception as e:
                stats['failed_rows'] += 1
                error_msg = f"Row {idx + 2}: {str(e)}"
                stats['errors'].append(error_msg)
                logger.error(f"Error processing row {idx + 2}: {e}")
                continue
        
        # Final commit
        await session.commit()
        
        logger.info(f"Import complete!")
        logger.info(f"  Total rows: {stats['total_rows']}")
        logger.info(f"  Imported leads: {stats['imported_leads']}")
        logger.info(f"  Imported campaign leads: {stats['imported_campaign_leads']}")
        logger.info(f"  Failed rows: {stats['failed_rows']}")
        
        return stats


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Import CSV training data into database')
    parser.add_argument('--csv', required=True, help='Path to CSV file')
    parser.add_argument('--user-id', required=True, type=UUID, help='User ID (UUID)')
    parser.add_argument('--campaign-name', default='ML Training Dataset', help='Campaign name')
    
    args = parser.parse_args()
    
    # Validate CSV file exists
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)
    
    try:
        stats = await import_csv_data(
            csv_path=args.csv,
            user_id=args.user_id,
            campaign_name=args.campaign_name
        )
        
        print("\n" + "="*50)
        print("IMPORT SUMMARY")
        print("="*50)
        print(f"Total rows processed: {stats['total_rows']}")
        print(f"Imported leads: {stats['imported_leads']}")
        print(f"Imported campaign leads: {stats['imported_campaign_leads']}")
        print(f"Failed rows: {stats['failed_rows']}")
        
        if stats['errors']:
            print(f"\nErrors ({len(stats['errors'])}):")
            for error in stats['errors'][:10]:  # Show first 10
                print(f"  - {error}")
            if len(stats['errors']) > 10:
                print(f"  ... and {len(stats['errors']) - 10} more errors")
        
        print("\nImport completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Import failed", exc_info=e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())




