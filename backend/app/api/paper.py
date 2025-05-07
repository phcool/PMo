from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body, Header
from typing import List, Optional
import logging
from datetime import datetime

from app.models.paper import Paper, PaperResponse, PaperAnalysisResponse
from app.services.db_service import db_service
from app.services.arxiv_service import ArxivService
from app.services.scheduler_service import scheduler_service
from app.services.paper_analysis_service import paper_analysis_service
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[PaperResponse])
async def get_papers(
    limit: int = Query(10, ge=1, le=100),
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
    
    # Get paper analysis results
    analysis = await db_service.get_paper_analysis(paper_id)
    
    # Convert to response model
    response = PaperResponse(
        paper_id=paper.paper_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        categories=paper.categories,
        pdf_url=paper.pdf_url,
        published_date=paper.published_date,
        updated_at=paper.updated_date,
        analysis=PaperAnalysisResponse(
            paper_id=analysis.paper_id,
            summary=analysis.summary,
            key_findings=analysis.key_findings,
            contributions=analysis.contributions,
            methodology=analysis.methodology,
            limitations=analysis.limitations,
            future_work=analysis.future_work,
            keywords=analysis.keywords,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at
        ) if analysis else None
    )
    
    return response

@router.post("/{paper_id}/analyze")
async def analyze_paper(paper_id: str):
    """
    Analyze the PDF content of the specified paper
    """
    # Check if paper exists
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Analyze paper
    analysis = await paper_analysis_service.analyze_paper(paper_id)
    if not analysis:
        raise HTTPException(status_code=500, detail="Failed to analyze paper")
    
    return {
        "status": "success",
        "message": "Paper analysis completed",
        "paper_id": paper_id,
        "timestamp": analysis.updated_at.isoformat()
    }

@router.get("/{paper_id}/analysis", response_model=PaperAnalysisResponse)
async def get_paper_analysis(paper_id: str):
    """
    Get the analysis results of a paper
    """
    # Check if paper exists
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Get analysis results
    analysis = await db_service.get_paper_analysis(paper_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis results found for this paper")
    
    return PaperAnalysisResponse(
        paper_id=analysis.paper_id,
        summary=analysis.summary,
        key_findings=analysis.key_findings,
        contributions=analysis.contributions,
        methodology=analysis.methodology,
        limitations=analysis.limitations,
        future_work=analysis.future_work,
        keywords=analysis.keywords,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at
    )

@router.post("/analyze-batch", status_code=202)
async def analyze_batch_papers():
    """
    Start batch paper analysis task
    """
    result = await paper_analysis_service.start_analysis_task()
    return result

@router.get("/recommend/")
async def get_recommended_papers(
    limit: int = Query(5, description="Number of recommended papers"),
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