"""
Leads API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.session import get_db
from src.api.middleware.auth import get_current_user
from src.models.user import User
from src.schemas.lead import LeadResponse, LeadListResponse, UploadLeadsResponse, LeadCreate
from src.services.lead_service import LeadService
from src.utils.csv_parser import parse_csv_file
from src.schemas.common import ApiResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/upload", response_model=ApiResponse)
async def upload_leads(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload CSV file with leads."""
    try:
        logger.info("Starting CSV upload", filename=file.filename, user_id=str(current_user.id))
        
        # Read file content
        content = await file.read()
        logger.info("File read", size=len(content))
        
        # Parse CSV
        valid_rows, errors = parse_csv_file(content)
        logger.info("CSV parsed", valid_rows=len(valid_rows), errors=len(errors))
        
        if not valid_rows:
            response_data = UploadLeadsResponse(imported=0, failed=0, errors=errors)
            response = ApiResponse(
                status="error",
                message="No valid leads found in CSV",
                data=response_data.model_dump()
            )
            logger.info("Returning error response - no valid rows")
            return response
        
        # Create leads
        lead_service = LeadService(db)
        leads_data = [LeadCreate(**row) for row in valid_rows]
        imported, failed, creation_errors = await lead_service.create_leads_batch(
            current_user.id,
            leads_data
        )
        logger.info("Leads created", imported=imported, failed=failed)
        
        # Combine errors
        all_errors = errors + creation_errors
        
        response_data = UploadLeadsResponse(
            imported=imported,
            failed=failed + len(errors),
            errors=all_errors[:10]  # Limit errors to first 10
        )
        response = ApiResponse(
            status="success",
            message=f"Imported {imported} leads, {failed} failed",
            data=response_data.model_dump()
        )
        logger.info("Returning success response")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception("Error uploading leads", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing CSV file: {str(e)}"
        )


# TEMPORARY: Test endpoint without auth
@router.post("/upload-test", response_model=ApiResponse)
async def upload_leads_test(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload CSV file with leads - TEST VERSION WITHOUT AUTH."""
    try:
        content = await file.read()
        valid_rows, errors = parse_csv_file(content)
        
        return ApiResponse(
            status="success" if valid_rows else "error",
            message=f"Found {len(valid_rows)} valid rows, {len(errors)} errors",
            data=UploadLeadsResponse(
                imported=len(valid_rows),
                failed=len(errors),
                errors=errors[:10]
            )
        )
    except Exception as e:
        logger.exception("Error in test upload", exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ApiResponse)
async def list_leads(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all leads for the authenticated user."""
    try:
        lead_service = LeadService(db)
        leads, total = await lead_service.get_leads(
            current_user.id,
            page=page,
            page_size=page_size
        )
        
        return ApiResponse(
            status="success",
            message="Leads retrieved successfully",
            data=LeadListResponse(
                leads=[LeadResponse.model_validate(lead) for lead in leads],
                total=total,
                page=page,
                page_size=page_size
            ).model_dump()
        )
    except Exception as e:
        logger.exception("Error listing leads", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving leads"
        )

