from fastapi import APIRouter, HTTPException, Query, Depends, Path, Header, Body
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import json

from app.models.paper import Paper, PaperResponse
from app.services.db_service import db_service
from app.services.arxiv_service import ArxivService
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[PaperResponse])
async def get_papers(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get recent papers (with pagination)
    """
    papers = await db_service.get_recent_papers(limit=limit, offset=offset)
    return papers


@router.get("/count")
async def count_papers():
    """
    Get the total number of papers in the database
    """
    count = await db_service.count_papers()
    return {"count": count}


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: str):
    """
    Get paper by ID
    """
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Convert to response model
    response = PaperResponse(
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

@router.get("/recommend/")
async def get_recommended_papers(
    limit: int = Query(30, description="Number of recommended papers"),
    offset: int = Query(0, description="Recommended papers offset"),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Get recommended papers based on user profile, or provide random papers from popular categories for new users
    """
    recommended_papers = []
    
    if x_user_id:
        # Try to get personalized recommendations
        recommended_papers = await recommendation_service.recommend_papers(user_id=x_user_id, limit=limit, offset=offset)
        
    # If no personalized recommendation results (possibly new user or insufficient history)
    if not recommended_papers:
        logger.info(f"User {x_user_id or 'anonymous'} has no personalized recommendations, providing random recommendations from popular categories")
        popular_categories = ["cs.CV", "cs.AI", "cs.LG", "cs.CL"]  # Define popular categories
        recommended_papers = await db_service.get_random_papers_by_category(categories=popular_categories, limit=limit, offset=offset)
        
    return recommended_papers 

@router.post("/search")
async def search_papers(
    query: Dict[str, str] = Body(..., description="Search query"),
    limit: int = Query(5, description="Maximum number of results", ge=1, le=20)
):
    """
    Search for papers directly based on a query string
    
    Returns a list of relevant papers that match the query
    """
    try:
        # 从请求体中获取查询文本
        query_text = query.get("query", "")
        
        if not query_text or len(query_text.strip()) == 0:
            return {"papers": []}
            
        logger.info(f"Paper search request with query: '{query_text}'")
        
        # 使用向量搜索获取相关论文
        paper_ids = await vector_search_service.search(query_text, k=limit)
        
        if not paper_ids:
            logger.info(f"No papers found for query: '{query_text}'")
            return {"papers": []}
        
        # 获取论文详细信息
        papers = []
        for paper_id in paper_ids:
            paper = await db_service.get_paper_by_id(paper_id)
            if paper:
                papers.append({
                    "title": paper.title,
                    "authors": paper.authors,
                    "categories": paper.categories,
                    "url": paper.pdf_url or ""
                })
        
        logger.info(f"Found {len(papers)} papers for query: '{query_text}'")
        return {"papers": papers}
        
    except Exception as e:
        logger.error(f"Error searching for papers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching for papers: {str(e)}") 