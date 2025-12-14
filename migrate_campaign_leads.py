"""
Migration script to add missing columns to campaign_leads table.
Run this script to sync the database schema with the model.
"""
import asyncio
from sqlalchemy import text
from src.database.session import async_engine, DATABASE_URL


async def migrate_campaign_leads():
    """Add missing columns to campaign_leads table."""
    print(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    
    async with async_engine.begin() as conn:
        print("Adding missing columns to campaign_leads table...")
        
        # List of columns to add with their SQL definitions
        columns = [
            ("subject", "VARCHAR(500)"),
            ("body", "TEXT"),
            ("sent", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("sent_at", "TIMESTAMP WITH TIME ZONE"),
            ("opened", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("clicked", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("replied", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("bounced", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("resend_message_id", "VARCHAR(255)"),
        ]
        
        for column_name, column_def in columns:
            # Check if column exists
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'campaign_leads' 
                    AND column_name = :column_name
                )
            """)
            result = await conn.execute(check_query, {"column_name": column_name})
            exists = result.scalar()
            
            if not exists:
                add_query = text(f"""
                    ALTER TABLE campaign_leads 
                    ADD COLUMN {column_name} {column_def}
                """)
                await conn.execute(add_query)
                print(f"  ✓ Added column: {column_name}")
            else:
                print(f"  - Column already exists: {column_name}")
        
        print("\nMigration completed successfully!")
    
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_campaign_leads())
