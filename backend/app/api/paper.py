from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body, Header
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any, AsyncGenerator
import logging
from datetime import datetime
import json

from app.models.paper import Paper, PaperResponse, PaperAnalysisResponse
from app.services.db_service import db_service
from app.services.arxiv_service import ArxivService
from app.services.paper_analysis_service import paper_analysis_service
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service
from app.services.llm_service import llm_service
from pydantic import BaseModel

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

# Add this new model at the appropriate location
class ChatRequest(BaseModel):
    """Request model for paper chat"""
    message: str
    context_messages: Optional[List[Dict[str, str]]] = None

# Chat response model for streaming
class ChatResponseChunk:
    def __init__(self, content: str, done: bool = False):
        self.content = content
        self.done = done
    
    def to_json(self) -> str:
        return json.dumps({
            "content": self.content,
            "done": self.done
        })

@router.post("/{paper_id}/chat")
async def chat_with_paper(
    paper_id: str = Path(..., description="The ID of the paper to chat about"),
    chat_request: ChatRequest = Body(..., description="Chat request containing the message")
):
    """
    Chat with the LLM about a specific paper using streaming response
    """
    # Get paper details
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper with ID {paper_id} not found")
    
    # Get paper analysis if available
    analysis = await db_service.get_paper_analysis(paper_id)
    
    # Prepare system prompt with paper information
    system_prompt = f"""You are a helpful academic assistant that can discuss the paper titled "{paper.title}". 
    
Paper information:
- Title: {paper.title}
- Authors: {', '.join(paper.authors)}
- Abstract: {paper.abstract}
- Categories: {', '.join(paper.categories)}
"""

    # Add analysis information if available
    if analysis:
        system_prompt += f"""
Paper analysis:
- Summary: {analysis.summary if analysis.summary else 'Not available'}
- Key findings: {analysis.key_findings if analysis.key_findings else 'Not available'}
- Contributions: {analysis.contributions if analysis.contributions else 'Not available'}
- Methodology: {analysis.methodology if analysis.methodology else 'Not available'}
- Limitations: {analysis.limitations if analysis.limitations else 'Not available'}
- Future work: {analysis.future_work if analysis.future_work else 'Not available'}
"""

    system_prompt += "\nPlease provide insightful and accurate responses to questions about this paper. If a question is not related to this paper, you can answer based on your general knowledge but mention that it's not specifically addressed in the paper."

    # Prepare messages for the conversation
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add context messages if provided
    if chat_request.context_messages:
        messages.extend(chat_request.context_messages)
    
    # Add the current user message
    messages.append({"role": "user", "content": chat_request.message})
    
    # Create a streaming response generator
    async def stream_llm_response():
        try:
            stream_response = await llm_service.client.chat.completions.create(
                model=llm_service.conversation_model,
                messages=messages,
                temperature=llm_service.conversation_temperature,
                max_tokens=llm_service.max_tokens,
                stream=True
            )
            
            async for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield ChatResponseChunk(content=content).to_json() + "\n"
                    
            # Send a final "done" message
            yield ChatResponseChunk(content="", done=True).to_json() + "\n"
                
        except Exception as e:
            logging.error(f"Error in streaming chat response: {str(e)}")
            # Send an error message in the stream
            error_msg = "Sorry, I encountered an error while processing your request."
            yield ChatResponseChunk(content=error_msg, done=True).to_json() + "\n"

    # Return a streaming response
    return StreamingResponse(
        stream_llm_response(),
        media_type="text/event-stream"
    ) 