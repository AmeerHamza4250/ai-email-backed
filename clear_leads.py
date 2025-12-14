"""
Script to clear all leads data from the database.
Run this script to delete all leads before importing new data.
"""
import asyncio
from sqlalchemy import text
from src.database.session import async_engine, DATABASE_URL


async def clear_leads():
    """Delete all leads from the database."""
    print(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    
    async with async_engine.begin() as conn:
        print("Clearing all leads data...")
        
        # Delete in correct order due to foreign key constraints
        # 1. Delete email_events (referenced by campaign_leads)
        print("Deleting email events...")
        email_events_query = text("DELETE FROM email_events")
        email_events_result = await conn.execute(email_events_query)
        print(f"  ✓ Deleted {email_events_result.rowcount} email events")
        
        # 2. Delete campaign_leads (references leads)
        print("Deleting campaign leads...")
        campaign_leads_query = text("DELETE FROM campaign_leads")
        campaign_leads_result = await conn.execute(campaign_leads_query)
        print(f"  ✓ Deleted {campaign_leads_result.rowcount} campaign leads")
        
        # 3. Delete leads
        print("Deleting leads...")
        leads_query = text("DELETE FROM leads")
        leads_result = await conn.execute(leads_query)
        print(f"  ✓ Deleted {leads_result.rowcount} leads")
        
        print("\n✓ All leads data cleared successfully!")
        print("You can now upload new CSV data.")
    
    await async_engine.dispose()


if __name__ == "__main__":
    confirm = input("Are you sure you want to delete ALL leads? This cannot be undone. Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        asyncio.run(clear_leads())
    else:
        print("Operation cancelled.")
