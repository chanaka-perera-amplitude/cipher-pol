# routes/health.py
from fastapi import APIRouter, status

# Create a new APIRouter instance
# This allows us to group related endpoints
router = APIRouter(
    prefix="/health",  
    tags=["Health"],
)

@router.get("", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.
    Returns a simple status indicating the service is up and running.
    """
    return {"status": "healthy", "message": "Cipher Pol agent service is currently operational"}
