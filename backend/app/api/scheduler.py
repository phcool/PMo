from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Optional
import logging

from app.services.scheduler_service import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status")
async def get_scheduler_status():
    """
    Get the status of the paper fetch and analysis scheduler
    """
    return scheduler_service.status

@router.post("/fetch")
async def manual_fetch_papers(
    categories: Optional[List[str]] = Body(None),
    max_results: int = Body(50)
):
    """
    Manually trigger the paper fetch task
    """
    result = await scheduler_service.manual_fetch(categories=categories, max_results=max_results)
    return result

@router.post("/analyze")
async def manual_analyze_papers():
    """
    Manually trigger the paper analysis task
    """
    result = await scheduler_service.manual_analyze()
    return result

@router.post("/start")
async def start_scheduler():
    """
    Start the paper fetch and analysis scheduler
    """
    try:
        scheduler_service.start()
        return {"status": "success", "message": "Paper fetch and analysis scheduler started"}
    except Exception as e:
        logger.error(f"Failed to start the scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start the scheduler: {str(e)}")

@router.post("/stop")
async def stop_scheduler():
    """
    Stop the paper fetch and analysis scheduler
    """
    try:
        scheduler_service.stop()
        return {"status": "success", "message": "Paper fetch and analysis scheduler stopped"}
    except Exception as e:
        logger.error(f"Failed to stop the scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop the scheduler: {str(e)}") 