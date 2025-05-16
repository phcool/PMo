from fastapi import APIRouter, HTTPException, Header, Depends, Body, Path, Query
from typing import Dict, Optional, Any, List

from app.models.user import UserPreferences, UserPreferencesResponse, UserSearchHistory, SearchHistoryItem, UserPaperViews
from app.services.db_service import db_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/user", response_model=UserPreferencesResponse)
async def get_user(x_user_id: Optional[str] = Header(None, description="User unique identifier"),
                  x_forwarded_for: Optional[str] = Header(None, description="User IP address")):
    """
    Get user access records
    """
    # If no user ID is provided, return default records
    if not x_user_id:
        return UserPreferencesResponse(
            user_id="anonymous",
            ip_prefix=None,
            last_visited_at=None,
            created_at=None
        )
    
    # Get user access records
    user_prefs = await db_service.get_user_preferences(x_user_id)
    
    # If user records don't exist, create a new one
    if not user_prefs:
        # Extract IP prefix from X-Forwarded-For
        ip_prefix = None
        if x_forwarded_for:
            ip_parts = x_forwarded_for.split(',')[0].strip().split('.')
            if len(ip_parts) >= 2:
                ip_prefix = '.'.join(ip_parts[:2])  # Take the first two parts of the IP address
        
        user_prefs = UserPreferences(user_id=x_user_id, ip_prefix=ip_prefix)
        await db_service.save_user_preferences(user_prefs)
    
    return UserPreferencesResponse(
        user_id=user_prefs.user_id,
        ip_prefix=user_prefs.ip_prefix,
        last_visited_at=user_prefs.last_visited_at,
        created_at=user_prefs.created_at
    )

@router.post("/user", response_model=UserPreferencesResponse)
async def save_user(
    x_user_id: Optional[str] = Header(None, description="User unique identifier"),
    x_forwarded_for: Optional[str] = Header(None, description="User IP address")
):
    """
    Update user access records
    """
    # If no user ID is provided, return error
    if not x_user_id:
        raise HTTPException(status_code=400, detail="User ID required to update access records")
    
    # Extract IP prefix from X-Forwarded-For
    ip_prefix = None
    if x_forwarded_for:
        ip_parts = x_forwarded_for.split(',')[0].strip().split('.')
        if len(ip_parts) >= 2:
            ip_prefix = '.'.join(ip_parts[:2])  # Take the first two parts of the IP address
    
    # Get existing records
    user_prefs = await db_service.get_user_preferences(x_user_id)
    
    if not user_prefs:
        # Create new records
        user_prefs = UserPreferences(user_id=x_user_id, ip_prefix=ip_prefix)
    else:
        # Update IP prefix
        user_prefs.ip_prefix = ip_prefix
    
    # Save records
    success = await db_service.save_user_preferences(user_prefs)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save user access records")
    
    # Get records again to return the latest timestamp
    updated_prefs = await db_service.get_user_preferences(x_user_id)
    if not updated_prefs:
        raise HTTPException(status_code=500, detail="Failed to retrieve user access records after saving")
    
    return UserPreferencesResponse(
        user_id=updated_prefs.user_id,
        ip_prefix=updated_prefs.ip_prefix,
        last_visited_at=updated_prefs.last_visited_at,
        created_at=updated_prefs.created_at
    )

# Keep old paths for backward compatibility
@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(x_user_id: Optional[str] = Header(None, description="User unique identifier"),
                             x_forwarded_for: Optional[str] = Header(None, description="User IP address")):
    """
    Get user access records (backward compatibility path)
    """
    return await get_user(x_user_id, x_forwarded_for)

@router.post("/preferences", response_model=UserPreferencesResponse)
async def save_user_preferences(
    x_user_id: Optional[str] = Header(None, description="User unique identifier"),
    x_forwarded_for: Optional[str] = Header(None, description="User IP address")
):
    """
    Update user access records (backward compatibility path)
    """
    return await save_user(x_user_id, x_forwarded_for)

@router.post("/search-history")
async def save_search_history(
    search_data: Dict[str, str] = Body(..., description="Search query data"),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Save user search history
    """
    # If no user ID is provided, don't save search history
    if not x_user_id:
        return {
            "status": "warning",
            "message": "No user ID provided, search history not saved"
        }
    
    query = search_data.get("query")
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    # Save search history
    success = await db_service.save_search_history(x_user_id, query.strip())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save search history")
    
    return {
        "status": "success",
        "message": "Search history saved",
        "user_id": x_user_id,
        "query": query.strip()
    }

@router.get("/search-history")
async def get_search_history(
    limit: int = Query(30, ge=1, le=50, description="Number of search history items to return"),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Get user search history
    """
    # If no user ID is provided, return empty list
    if not x_user_id:
        return {
            "user_id": "anonymous",
            "searches": [],
            "updated_at": None
        }
    
    # Get search history
    history = await db_service.get_search_history(x_user_id, limit)
    
    return {
        "user_id": history.user_id,
        "searches": [{"query": item.query, "timestamp": item.timestamp} for item in history.searches],
        "updated_at": history.updated_at
    }

@router.post("/paper-views")
async def record_paper_view_body(
    data: Dict[str, str] = Body(..., description="Paper view data containing paper_id"),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Record user paper viewing history using POST with request body
    """
    # If no user ID is provided, don't record viewing
    if not x_user_id:
        return {
            "success": False,
            "message": "No user ID provided, viewing record not saved"
        }
    
    paper_id = data.get("paper_id")
    if not paper_id:
        raise HTTPException(status_code=400, detail="Missing required parameter 'paper_id'")
    
    success = await db_service.record_paper_view(user_id=x_user_id, paper_id=paper_id)
    
    if not success:
        logger.warning(f"Failed to record paper viewing history: user_id={x_user_id}, paper_id={paper_id}")
    
    return {
        "success": success,
        "user_id": x_user_id,
        "paper_id": paper_id,
        "message": "Viewing record saved" if success else "Failed to record viewing record"
    }

@router.post("/paper-view/{paper_id}")
async def record_paper_view(
    paper_id: str = Path(..., description="Paper ID"),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Record user paper viewing history
    """
    # If no user ID is provided, don't record viewing
    if not x_user_id:
        return {
            "success": False,
            "message": "No user ID provided, viewing record not saved"
        }
    
    if not paper_id:
        raise HTTPException(status_code=400, detail="Missing required parameter")
    
    success = await db_service.record_paper_view(user_id=x_user_id, paper_id=paper_id)
    
    if not success:
        logger.warning(f"Failed to record paper viewing history: user_id={x_user_id}, paper_id={paper_id}")
    
    return {
        "success": success,
        "user_id": x_user_id,
        "paper_id": paper_id,
        "message": "Viewing record saved" if success else "Failed to record viewing record"
    }

@router.get("/paper-views", response_model=UserPaperViews)
async def get_user_paper_views(
    limit: int = Query(30, description="Maximum number of records to return", ge=1, le=50),
    days: int = Query(30, description="Only return records from the past number of days", ge=1, le=365),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Get user paper viewing history
    """
    # If no user ID is provided, return empty list
    if not x_user_id:
        return UserPaperViews(
            user_id="anonymous",
            views=[],
            updated_at=None
        )
    
    views = await db_service.get_user_paper_views(
        user_id=x_user_id,
        limit=limit,
        days=days
    )
    
    return views 