from fastapi import APIRouter, HTTPException, Body, Path, UploadFile, File, Form, Request, Response, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
import json
import uuid
from datetime import datetime

from app.services.chat_service import chat_service
from app.services.db_service import db_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Request and response models
class ChatSessionResponse(BaseModel):
    chat_id: str
    paper_id: Optional[str] = None
    created_at: datetime

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str

class ChatResponseChunk:
    def __init__(self, content: str, done: bool = False):
        self.content = content
        self.done = done
    
    def to_json(self) -> str:
        return json.dumps({
            "content": self.content,
            "done": self.done
        })

# Create a new chat session
@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    paper_id: Optional[str] = Query(None, description="Optional paper ID if chatting about a specific paper")
):
    """
    Create a new chat session, optionally linked to a paper
    """
    # Validate paper ID if provided
    if paper_id:
        paper = await db_service.get_paper_by_id(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper with ID {paper_id} not found")
    
    # Create chat session
    chat_id = chat_service.create_chat_session(paper_id)
    
    return ChatSessionResponse(
        chat_id=chat_id,
        paper_id=paper_id,
        created_at=datetime.now()
    )

# Upload a PDF for RAG
@router.post("/sessions/{chat_id}/upload")
async def upload_pdf(
    chat_id: str = Path(..., description="Chat session ID"),
    file: UploadFile = File(..., description="PDF file to upload")
):
    """
    Upload a PDF file for a chat session to enable RAG functionality
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Process PDF
        success = await chat_service.process_pdf(chat_id, file_content, file.filename)
        
        if not success:
            # 设置会话状态为非处理中
            if chat_id in chat_service.processing_files:
                chat_service.processing_files[chat_id] = {"processing": False, "file_name": file.filename}
            
            # 返回错误，但使用422而不是500，表示请求格式正确但内容处理失败
            raise HTTPException(
                status_code=422, 
                detail="Failed to process PDF file. This could be due to file format issues or API limitations. Try a simpler or smaller PDF."
            )
        
        return {"message": "PDF file processed successfully", "filename": file.filename}
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing PDF upload: {str(e)}")
        # 设置会话状态为非处理中
        if chat_id in chat_service.processing_files:
            chat_service.processing_files[chat_id] = {"processing": False, "file_name": file.filename}
        
        # 对意外异常返回500错误
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while processing the PDF: {str(e)}"
        )

# Get chat messages
@router.get("/sessions/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str = Path(..., description="Chat session ID"),
    limit: Optional[int] = Query(None, description="Maximum number of messages to return")
):
    """
    Get messages from a chat session
    """
    messages = chat_service.get_messages(chat_id, limit)
    return {"messages": messages}

# 获取文件处理状态
@router.get("/sessions/{chat_id}/processing-status")
async def get_processing_status(
    chat_id: str = Path(..., description="Chat session ID")
):
    """
    获取指定会话的文件处理状态
    """
    status = chat_service.is_processing_file(chat_id)
    
    # 获取会话中的文件总数（如果存在）
    if chat_id in chat_service.active_chats and "files" in chat_service.active_chats[chat_id]:
        files_count = len(chat_service.active_chats[chat_id]["files"])
        if "files_count" not in status:
            status["files_count"] = files_count
    
    return status

# Send message and get response
@router.post("/sessions/{chat_id}/chat")
async def chat_with_session(
    chat_id: str = Path(..., description="Chat session ID"),
    chat_request: ChatRequest = Body(..., description="Chat request containing the message")
):
    """
    Send a message to a chat session and get a streaming response
    """
    # 检查是否正在处理文件，如果是则拒绝请求
    status = chat_service.is_processing_file(chat_id)
    if status["processing"]:
        raise HTTPException(
            status_code=423,  # Locked
            detail=f"Cannot send messages while processing file: {status['file_name']}. Please wait until processing is complete."
        )
    
    # Check if this chat is linked to a paper
    paper = None
    paper_id = None
    
    if chat_id in chat_service.active_chats:
        paper_id = chat_service.active_chats[chat_id].get("paper_id")
        
        if paper_id:
            paper = await db_service.get_paper_by_id(paper_id)
    
    # Create streaming response
    async def stream_chat_response():
        async for content_chunk, is_done in chat_service.generate_response(chat_id, chat_request.message, paper):
            yield ChatResponseChunk(content=content_chunk, done=is_done).to_json() + "\n"
    
    return StreamingResponse(
        stream_chat_response(),
        media_type="text/event-stream"
    )

# End chat session
@router.delete("/sessions/{chat_id}")
async def end_chat_session(
    chat_id: str = Path(..., description="Chat session ID")
):
    """
    End a chat session and clean up resources
    """
    success = await chat_service.end_chat_session(chat_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {chat_id} not found or already ended"
        )
        
    return {"message": "Chat session ended successfully. Files will be automatically cleaned up after the expiry period."} 