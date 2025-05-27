from fastapi import APIRouter, HTTPException, Query
from typing import List
import logging

from app.models.paper import Paper
from app.services.db_service import db_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[Paper])
async def get_papers(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get recent papers from database
    """
    papers = await db_service.get_recent_papers(limit=limit, offset=offset)
    return papers


@router.get("/count")
async def count_papers():
    """
    Get the total number of papers in the database
    """
    count = await db_service.count_papers()
    return count


@router.get("/{paper_id}", response_model=Paper)
async def get_paper(paper_id: str):
    """
    Get paper by paper_id
    """
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    response = Paper(
        paper_id=paper.paper_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        categories=paper.categories,
        pdf_url=paper.pdf_url,
        published_date=paper.published_date,
        updated_at=paper.updated_date
    )
    
    return response 