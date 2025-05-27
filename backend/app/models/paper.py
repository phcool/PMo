from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Paper(BaseModel):
    """Paper model for storing data"""
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    pdf_url: str
    published_date: datetime
    updated_date: Optional[datetime] = None
    


class PaperSearchRequest(BaseModel):
    """Model for paper search request"""
    query: str
    limit: int = Field(30, ge=1, le=100)
    categories: Optional[List[str]] = Field(None)


class PaperSearchResponse(BaseModel):
    """Model for paper search response"""
    results: List[Paper]
    count: int 