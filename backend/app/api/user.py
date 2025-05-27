import uuid
from fastapi import APIRouter

router = APIRouter()

@router.post("/get_id")
async def generate_user_id():
    """
    Generate a unique user ID.
    """
    user_id = uuid.uuid4()
    return str(user_id)
