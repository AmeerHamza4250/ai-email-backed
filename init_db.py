"""
Initialize database tables.
Run this script to create all database tables.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from src.database.base import Base
from src.database.session import DATABASE_URL
# Import all models to register them with Base
from src.models.user import User
from src.models.campaign import Campaign
from src.models.lead import Lead
from src.models.campaign_lead import CampaignLead
from src.models.email_event import EmailEvent
from src.models.ml_model import MLModel
from src.models.ml_prediction import MLPrediction

async def init_db():
    """Create all database tables."""
    print(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        print("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())

