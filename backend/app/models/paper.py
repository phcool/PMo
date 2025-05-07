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
    
    class Config:
        json_schema_extra = {
            "example": {
                "paper_id": "2105.12345",
                "title": "Advances in Deep Learning",
                "authors": ["John Smith", "Jane Doe"],
                "abstract": "This paper presents advances in deep learning...",
                "categories": ["cs.LG", "cs.AI"],
                "pdf_url": "https://arxiv.org/pdf/2105.12345.pdf",
                "published_date": "2023-05-20T00:00:00",
                "updated_date": "2023-05-25T00:00:00"
            }
        }


class PaperAnalysis(BaseModel):
    """Paper PDF analysis result model"""
    paper_id: str = Field(..., description="Paper ID")
    summary: Optional[str] = Field(None, description="Paper summary")
    key_findings: Optional[str] = Field(None, description="Key findings")
    contributions: Optional[str] = Field(None, description="Main contributions")
    methodology: Optional[str] = Field(None, description="Methodology")
    limitations: Optional[str] = Field(None, description="Limitations")
    future_work: Optional[str] = Field(None, description="Future work")
    keywords: Optional[str] = Field(None, description="Paper keywords")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")


class PaperAnalysisResponse(BaseModel):
    """Paper PDF analysis result response model"""
    paper_id: str
    summary: Optional[str] = None
    key_findings: Optional[str] = None
    contributions: Optional[str] = None
    methodology: Optional[str] = None
    limitations: Optional[str] = None
    future_work: Optional[str] = None
    keywords: Optional[str] = None
    created_at: datetime
    updated_at: datetime


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
    analysis: Optional[PaperAnalysisResponse] = None


class PaperSearchRequest(BaseModel):
    """Model for paper search request"""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Maximum number of results to return", ge=1, le=100)
    categories: Optional[List[str]] = Field(None, description="Filter by categories")


class PaperSearchResponse(BaseModel):
    """Model for paper search response"""
    results: List[PaperResponse]
    count: int 