from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Optional
import logging

from app.services.scheduler_service import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status")
async def get_scheduler_status():
    """
    获取论文获取定时任务的状态
    """
    return scheduler_service.status

@router.post("/fetch")
async def manual_fetch_papers(
    categories: Optional[List[str]] = Body(None),
    max_results: int = Body(50)
):
    """
    手动触发论文获取任务
    """
    result = await scheduler_service.manual_fetch(categories=categories, max_results=max_results)
    return result

@router.post("/start")
async def start_scheduler():
    """
    启动论文获取定时任务
    """
    try:
        scheduler_service.start()
        return {"status": "success", "message": "论文获取定时任务已启动"}
    except Exception as e:
        logger.error(f"启动定时任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动定时任务失败: {str(e)}")

@router.post("/stop")
async def stop_scheduler():
    """
    停止论文获取定时任务
    """
    try:
        scheduler_service.stop()
        return {"status": "success", "message": "论文获取定时任务已停止"}
    except Exception as e:
        logger.error(f"停止定时任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止定时任务失败: {str(e)}") 