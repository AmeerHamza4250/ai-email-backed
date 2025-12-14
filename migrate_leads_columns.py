"""
Migration script to add CSV fields to leads table.
Run this script to sync the database schema with the model.
"""
import asyncio
from sqlalchemy import text
from src.database.session import async_engine, DATABASE_URL


async def migrate_leads():
    """Add CSV fields to leads table."""
    print(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    
    async with async_engine.begin() as conn:
        print("Adding CSV fields to leads table...")
        
        # List of columns to add with their SQL definitions
        columns = [
            ("email_id", "VARCHAR(255)"),
            ("email_subject", "VARCHAR(500)"),
            ("email_type", "VARCHAR(255)"),
            ("sent_status", "VARCHAR(50)"),
            ("reply_status", "VARCHAR(50)"),
            ("time_to_reply_hours", "VARCHAR(50)"),
        ]
        
        for column_name, column_def in columns:
            # Check if column exists
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'leads' 
                    AND column_name = :column_name
                )
            """)
            result = await conn.execute(check_query, {"column_name": column_name})
            exists = result.scalar()
            
            if not exists:
                add_query = text(f"""
                    ALTER TABLE leads 
                    ADD COLUMN {column_name} {column_def}
                """)
                await conn.execute(add_query)
                print(f"  ✓ Added column: {column_name}")
            else:
                print(f"  - Column already exists: {column_name}")
        
        # Add index on email_id if it doesn't exist
        index_check_query = text("""
            SELECT EXISTS (
                SELECT 1 
                FROM pg_indexes 
                WHERE tablename = 'leads' 
                AND indexname = 'idx_leads_email_id'
            )
        """)
        index_result = await conn.execute(index_check_query)
        index_exists = index_result.scalar()
        
        if not index_exists:
            index_query = text("CREATE INDEX idx_leads_email_id ON leads(email_id)")
            await conn.execute(index_query)
            print("  ✓ Added index on email_id")
        else:
            print("  - Index on email_id already exists")
        
        print("\nMigration completed successfully!")
    
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_leads())
