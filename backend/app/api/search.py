from fastapi import APIRouter, HTTPException, Query, Depends, Body
from typing import List, Optional
import logging

from app.models.paper import PaperSearchRequest, PaperSearchResponse, PaperResponse
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=PaperSearchResponse)
async def search_papers(search_request: PaperSearchRequest):
    """
    Search for papers using vector search
    """
    try:
        # Get paper IDs matching the query
        paper_ids = await vector_search_service.search(
            query=search_request.query,
            k=search_request.limit
        )
        
        if not paper_ids:
            return PaperSearchResponse(results=[], count=0)
        
        # Get paper details from the database
        papers = await db_service.get_papers_by_ids(paper_ids)
        
        # Filter by categories if specified
        if search_request.categories:
            papers = [
                p for p in papers if any(
                    cat in p.categories for cat in search_request.categories
                )
            ]
        
        # Convert to response model
        paper_responses = [
            PaperResponse(
                paper_id=p.paper_id,
                title=p.title,
                authors=p.authors,
                abstract=p.abstract,
                categories=p.categories,
                pdf_url=p.pdf_url,
                published_date=p.published_date,
                updated_date=p.updated_date
            ) for p in papers
        ]
        
        return PaperSearchResponse(
            results=paper_responses,
            count=len(paper_responses)
        )
        
    except Exception as e:
        logger.error(f"Error searching papers: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error searching papers: {str(e)}"
        ) 