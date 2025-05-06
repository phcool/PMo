from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class UserPreferences(BaseModel):
    """用户偏好设置模型"""
    user_id: str = Field(..., description="用户唯一标识")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="用户偏好设置")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

class UserPreferencesResponse(BaseModel):
    """用户偏好设置响应模型"""
    user_id: str
    preferences: Dict[str, Any]
    updated_at: Optional[datetime] = None

class SearchHistoryItem(BaseModel):
    """搜索历史项目模型"""
    query: str = Field(..., description="搜索查询")
    timestamp: datetime = Field(..., description="搜索时间")

class UserSearchHistory(BaseModel):
    """用户搜索历史模型"""
    user_id: str = Field(..., description="用户唯一标识")
    searches: List[SearchHistoryItem] = Field(default=[], description="搜索历史列表")
    updated_at: Optional[datetime] = Field(None, description="最后更新时间")

class UserSearchHistoryResponse(BaseModel):
    """用户搜索历史响应模型"""
    user_id: str
    searches: List[SearchHistoryItem]
    updated_at: Optional[datetime] = None

class PaperViewItem(BaseModel):
    """论文浏览记录项"""
    paper_id: str = Field(..., description="论文ID")
    title: Optional[str] = Field(None, description="论文标题")
    view_date: datetime = Field(..., description="浏览日期")
    view_count: int = Field(1, description="浏览次数")
    first_viewed_at: datetime = Field(..., description="首次浏览时间")
    last_viewed_at: datetime = Field(..., description="最近浏览时间")

class UserPaperViews(BaseModel):
    """用户论文浏览历史"""
    user_id: str = Field(..., description="用户ID")
    views: List[PaperViewItem] = Field(default=[], description="论文浏览记录")
    updated_at: Optional[datetime] = Field(None, description="最后更新时间") 