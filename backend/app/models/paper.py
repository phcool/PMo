from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Paper(BaseModel):
    """Paper model for storing arXiv paper data"""
    paper_id: str = Field(..., description="arXiv paper ID")
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(default=[], description="List of authors")
    abstract: str = Field(..., description="Paper abstract")
    categories: List[str] = Field(default=[], description="arXiv categories")
    pdf_url: str = Field(..., description="URL to PDF")
    published_date: datetime = Field(..., description="Publication date")
    updated_date: Optional[datetime] = Field(None, description="Last updated date")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding for search")
    


class PaperResponse(BaseModel):
    """Model for paper response without embeddings"""
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    pdf_url: str
    published_date: datetime
    updated_at: Optional[datetime] = None


class PaperSearchRequest(BaseModel):
    """Model for paper search request"""
    query: str = Field(..., description="Search query")
    limit: int = Field(30, description="Maximum number of results to return", ge=1, le=100)
    categories: Optional[List[str]] = Field(None, description="Filter by categories")


class PaperSearchResponse(BaseModel):
    """Model for paper search response"""
    results: List[PaperResponse]
    count: int 