from fastapi import APIRouter, HTTPException, Header, Depends, Body, Path, Query
from typing import Dict, Optional, Any, List

from app.models.user import UserPreferences, UserPreferencesResponse, UserSearchHistory, SearchHistoryItem, UserPaperViews
from app.services.db_service import db_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/user", response_model=UserPreferencesResponse)
async def get_user(x_user_id: Optional[str] = Header(None, description="用户唯一标识"),
                  x_forwarded_for: Optional[str] = Header(None, description="用户IP地址")):
    """
    获取用户访问记录
    """
    # 如果没有提供用户ID，返回默认记录
    if not x_user_id:
        return UserPreferencesResponse(
            user_id="anonymous",
            ip_prefix=None,
            last_visited_at=None,
            created_at=None
        )
    
    # 获取用户访问记录
    user_prefs = await db_service.get_user_preferences(x_user_id)
    
    # 如果用户记录不存在，创建一个新的
    if not user_prefs:
        # 从 X-Forwarded-For 提取 IP 前缀
        ip_prefix = None
        if x_forwarded_for:
            ip_parts = x_forwarded_for.split(',')[0].strip().split('.')
            if len(ip_parts) >= 2:
                ip_prefix = '.'.join(ip_parts[:2])  # 取IP地址的前两部分
        
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
    x_user_id: Optional[str] = Header(None, description="用户唯一标识"),
    x_forwarded_for: Optional[str] = Header(None, description="用户IP地址")
):
    """
    更新用户访问记录
    """
    # 如果没有提供用户ID，返回错误
    if not x_user_id:
        raise HTTPException(status_code=400, detail="更新访问记录需要用户ID")
    
    # 从 X-Forwarded-For 提取 IP 前缀
    ip_prefix = None
    if x_forwarded_for:
        ip_parts = x_forwarded_for.split(',')[0].strip().split('.')
        if len(ip_parts) >= 2:
            ip_prefix = '.'.join(ip_parts[:2])  # 取IP地址的前两部分
    
    # 获取现有记录
    user_prefs = await db_service.get_user_preferences(x_user_id)
    
    if not user_prefs:
        # 创建新记录
        user_prefs = UserPreferences(user_id=x_user_id, ip_prefix=ip_prefix)
    else:
        # 更新IP前缀
        user_prefs.ip_prefix = ip_prefix
    
    # 保存记录
    success = await db_service.save_user_preferences(user_prefs)
    if not success:
        raise HTTPException(status_code=500, detail="无法保存用户访问记录")
    
    # 重新获取记录以返回最新的时间戳
    updated_prefs = await db_service.get_user_preferences(x_user_id)
    if not updated_prefs:
        raise HTTPException(status_code=500, detail="保存后无法获取用户访问记录")
    
    return UserPreferencesResponse(
        user_id=updated_prefs.user_id,
        ip_prefix=updated_prefs.ip_prefix,
        last_visited_at=updated_prefs.last_visited_at,
        created_at=updated_prefs.created_at
    )

# 保留旧路径进行向后兼容
@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(x_user_id: Optional[str] = Header(None, description="用户唯一标识"),
                             x_forwarded_for: Optional[str] = Header(None, description="用户IP地址")):
    """
    获取用户访问记录（兼容旧路径）
    """
    return await get_user(x_user_id, x_forwarded_for)

@router.post("/preferences", response_model=UserPreferencesResponse)
async def save_user_preferences(
    x_user_id: Optional[str] = Header(None, description="用户唯一标识"),
    x_forwarded_for: Optional[str] = Header(None, description="用户IP地址")
):
    """
    更新用户访问记录（兼容旧路径）
    """
    return await save_user(x_user_id, x_forwarded_for)

@router.post("/search-history")
async def save_search_history(
    search_data: Dict[str, str] = Body(..., description="搜索查询数据"),
    x_user_id: Optional[str] = Header(None, description="用户唯一标识")
):
    """
    保存用户搜索历史
    """
    # 如果没有提供用户ID，不保存搜索历史
    if not x_user_id:
        return {
            "status": "warning",
            "message": "未提供用户ID，搜索历史未保存"
        }
    
    query = search_data.get("query")
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="搜索查询不能为空")
    
    # 保存搜索历史
    success = await db_service.save_search_history(x_user_id, query.strip())
    if not success:
        raise HTTPException(status_code=500, detail="无法保存搜索历史")
    
    return {
        "status": "success",
        "message": "搜索历史已保存",
        "user_id": x_user_id,
        "query": query.strip()
    }

@router.get("/search-history")
async def get_search_history(
    limit: int = Query(10, ge=1, le=50, description="返回的搜索历史条数"),
    x_user_id: Optional[str] = Header(None, description="用户唯一标识")
):
    """
    获取用户搜索历史
    """
    # 如果没有提供用户ID，返回空列表
    if not x_user_id:
        return {
            "user_id": "anonymous",
            "searches": [],
            "updated_at": None
        }
    
    # 获取搜索历史
    history = await db_service.get_search_history(x_user_id, limit)
    
    return {
        "user_id": history.user_id,
        "searches": [{"query": item.query, "timestamp": item.timestamp} for item in history.searches],
        "updated_at": history.updated_at
    }

@router.post("/paper-view/{paper_id}")
async def record_paper_view(
    paper_id: str = Path(..., description="论文ID"),
    x_user_id: Optional[str] = Header(None, description="用户唯一标识")
):
    """
    记录用户论文浏览记录
    """
    # 如果没有提供用户ID，不记录浏览
    if not x_user_id:
        return {
            "success": False,
            "message": "未提供用户ID，浏览记录未保存"
        }
    
    if not paper_id:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    
    success = await db_service.record_paper_view(user_id=x_user_id, paper_id=paper_id)
    
    if not success:
        logger.warning(f"记录论文浏览记录失败: user_id={x_user_id}, paper_id={paper_id}")
    
    return {
        "success": success,
        "user_id": x_user_id,
        "paper_id": paper_id,
        "message": "浏览记录已保存" if success else "记录浏览记录失败"
    }

@router.get("/paper-views", response_model=UserPaperViews)
async def get_user_paper_views(
    limit: int = Query(20, description="最大返回数量", ge=1, le=50),
    days: int = Query(30, description="只返回最近多少天的记录", ge=1, le=365),
    x_user_id: Optional[str] = Header(None, description="用户唯一标识")
):
    """
    获取用户论文浏览记录
    """
    # 如果没有提供用户ID，返回空列表
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