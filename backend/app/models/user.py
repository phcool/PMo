from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class UserPreferences(BaseModel):
    """User access records model"""
    user_id: str = Field(..., description="User unique identifier")
    ip_prefix: Optional[str] = Field(None, description="First part of user's IP address")
    last_visited_at: datetime = Field(default_factory=datetime.now, description="Last visit time")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")

class UserPreferencesResponse(BaseModel):
    """User access records response model"""
    user_id: str
    ip_prefix: Optional[str] = None
    last_visited_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class SearchHistoryItem(BaseModel):
    """Search history item model"""
    query: str = Field(..., description="Search query")
    timestamp: datetime = Field(..., description="Search time")

class UserSearchHistory(BaseModel):
    """User search history model"""
    user_id: str = Field(..., description="User unique identifier")
    searches: List[SearchHistoryItem] = Field(default=[], description="Search history list")
    updated_at: Optional[datetime] = Field(None, description="Last update time")

class UserSearchHistoryResponse(BaseModel):
    """User search history response model"""
    user_id: str
    searches: List[SearchHistoryItem]
    updated_at: Optional[datetime] = None

class PaperViewItem(BaseModel):
    """Paper viewing record item"""
    paper_id: str = Field(..., description="Paper ID")
    title: Optional[str] = Field(None, description="Paper title")
    view_date: datetime = Field(..., description="View date")
    view_count: int = Field(1, description="View count")
    first_viewed_at: datetime = Field(..., description="First view time")
    last_viewed_at: datetime = Field(..., description="Most recent view time")

class UserPaperViews(BaseModel):
    """User paper viewing history"""
    user_id: str = Field(..., description="User ID")
    views: List[PaperViewItem] = Field(default=[], description="Paper viewing records")
    updated_at: Optional[datetime] = Field(None, description="Last update time") 