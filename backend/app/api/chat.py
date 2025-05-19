from fastapi import APIRouter, HTTPException, Body, Path, UploadFile, File, Form, Request, Response, Depends, Query
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
import json
import uuid
from datetime import datetime
import os

from app.services.chat_service import chat_service
from app.services.db_service import db_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Request and response models
class ChatSessionResponse(BaseModel):
    chat_id: str
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
        """
        将响应块转换为JSON字符串。
        这必须与前端的预期格式匹配，前端期望有content字段。
        """
        return json.dumps({
            "content": self.content,
            "done": self.done
        }, ensure_ascii=False)

# Request model for attaching paper to chat
class AttachPaperRequest(BaseModel):
    paper_id: str

# Create a new chat session
@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session():
    """
    Create a new chat session
    """
    
    # Create chat session
    chat_id = chat_service.create_chat_session()
    
    return ChatSessionResponse(
        chat_id=chat_id,
        created_at=datetime.now()
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
    
    # Check if chat session exists
    if chat_id not in chat_service.active_chats:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {chat_id} not found"
        )
    
    # Create streaming response
    async def stream_chat_response():
        try:
            logger.info(f"Starting stream for chat session {chat_id}")
            message_count = 0
            char_count = 0
            async for content_chunk, is_done in chat_service.generate_response(chat_id, chat_request.message):
                message_count += 1
                char_count += len(content_chunk) if content_chunk else 0
                response_chunk = ChatResponseChunk(content=content_chunk, done=is_done)
                json_chunk = response_chunk.to_json() + "\n"
                logger.debug(f"Streamed chunk {message_count}: len={len(content_chunk)} done={is_done}")
                yield json_chunk
            logger.info(f"Stream complete for chat session {chat_id}. Sent {message_count} chunks with {char_count} characters")
        except Exception as e:
            logger.error(f"Error in stream_chat_response: {str(e)}")
            # 发送错误消息
            error_chunk = ChatResponseChunk(content="Error processing request", done=True)
            yield error_chunk.to_json() + "\n"
    
    return StreamingResponse(
        stream_chat_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 防止Nginx缓冲
        }
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

# Get session files
@router.get("/sessions/{chat_id}/files")
async def get_session_files(
    chat_id: str = Path(..., description="Chat session ID")
):
    """
    Get files associated with a chat session
    """
    if chat_id not in chat_service.active_chats:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {chat_id} not found"
        )
    
    chat_data = chat_service.active_chats[chat_id]
    result = []
    
    # Check if the session has files
    if "files" in chat_data and chat_data["files"]:
        for idx, file_data in enumerate(chat_data["files"]):
            # Ensure each file has an ID
            if "id" not in file_data:
                file_data["id"] = str(uuid.uuid4())
            
            # Add to result list
            result.append({
                "id": file_data["id"],
                "name": file_data.get("filename", f"Document {idx+1}"),
                "size": os.path.getsize(file_data["file_path"]) if os.path.exists(file_data["file_path"]) else 0,
                "upload_time": datetime.now().isoformat()  # Fallback since we don't store upload time
            })
    
    return result

# View a file
@router.get("/files/{file_id}/view")
async def view_file(
    file_id: str = Path(..., description="File ID"),
    no_download: bool = Query(False, description="If true, file will be displayed in browser without download prompt")
):
    """
    View a file by its ID
    """
    # Search for the file in all active chat sessions
    for chat_id, chat_data in chat_service.active_chats.items():
        if "files" in chat_data:
            for file_data in chat_data["files"]:
                if file_data.get("id") == file_id:
                    file_path = file_data["file_path"]
                    if os.path.exists(file_path):
                        # 简化文件名以避免编码问题
                        safe_filename = "document.pdf"
                        
                        if no_download:
                            # 简化内联头信息，完全避免文件名编码问题
                            headers = {
                                "Content-Disposition": "inline",
                                "Content-Type": "application/pdf",
                                "X-Content-Type-Options": "nosniff"
                            }
                            return FileResponse(
                                path=file_path,
                                media_type="application/pdf",
                                headers=headers
                            )
                        else:
                            # 默认设置为attachment以提示下载，使用安全文件名
                            return FileResponse(
                                path=file_path, 
                                filename=safe_filename,
                                media_type="application/pdf"
                            )
    
    # If file not found
    raise HTTPException(
        status_code=404,
        detail=f"File with ID {file_id} not found"
    )

# Delete a file
@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str = Path(..., description="File ID")
):
    """
    Delete a file by its ID
    """
    # Search for the file in all active chat sessions
    for chat_id, chat_data in chat_service.active_chats.items():
        if "files" in chat_data:
            for idx, file_data in enumerate(chat_data["files"]):
                if file_data.get("id") == file_id:
                    file_name = file_data.get("filename", "document.pdf")
                    
                    # Remove from the session's files list
                    chat_service.active_chats[chat_id]["files"].pop(idx)
                    
                    return {"message": f"File {file_name} deleted successfully"}
    
    # If file not found
    raise HTTPException(
        status_code=404,
        detail=f"File with ID {file_id} not found"
    )

# Attach paper to chat session
@router.post("/sessions/{chat_id}/attach_paper")
async def attach_paper_to_chat(
    chat_id: str = Path(..., description="Chat session ID"),
    request: AttachPaperRequest = Body(..., description="Request with paper ID to attach")
):
    """
    Download a paper PDF from arXiv and associate it with a chat session
    """
    # Check if chat session exists
    if chat_id not in chat_service.active_chats:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {chat_id} not found"
        )
    
    # Validate paper exists in database
    paper = await db_service.get_paper_by_id(request.paper_id)
    if not paper:
        raise HTTPException(
            status_code=404,
            detail=f"Paper with ID {request.paper_id} not found"
        )
    
    try:
        success = await chat_service.get_paper_pdf(chat_id, request.paper_id)
        
        if not success:
            raise HTTPException(
                status_code=422, 
                detail=f"Failed to get PDF for paper {request.paper_id}. The PDF might not be available."
            )
        
        return {"success": True, "message": f"Paper {request.paper_id} successfully attached to chat session"}
    
    except Exception as e:
        logger.error(f"Error attaching paper {request.paper_id} to chat session {chat_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

# Process paper embeddings
@router.post("/sessions/{chat_id}/process_embeddings")
async def process_paper_embeddings(
    chat_id: str = Path(..., description="Chat session ID"),
    request: AttachPaperRequest = Body(..., description="Request with paper ID to process")
):
    """
    Process embeddings for a paper that has already been attached to the chat session
    """
    # Check if chat session exists
    if chat_id not in chat_service.active_chats:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {chat_id} not found"
        )
    
    # Validate paper exists in database
    paper = await db_service.get_paper_by_id(request.paper_id)
    if not paper:
        raise HTTPException(
            status_code=404,
            detail=f"Paper with ID {request.paper_id} not found"
        )
    
    try:
        # 只处理向量化
        success = await chat_service.process_paper_embeddings(chat_id, request.paper_id)
        
        if not success:
            raise HTTPException(
                status_code=422, 
                detail=f"Failed to process embeddings for paper {request.paper_id}."
            )
        
        return {"success": True, "message": f"Successfully processed embeddings for paper {request.paper_id}"}
    
    except Exception as e:
        logger.error(f"Error processing embeddings for paper {request.paper_id} in chat session {chat_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        ) 