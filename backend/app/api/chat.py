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
        """
        将响应块转换为JSON字符串。
        这必须与前端的预期格式匹配，前端期望有content字段。
        """
        return json.dumps({
            "content": self.content,
            "done": self.done
        }, ensure_ascii=False)

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
        
        # 获取文件信息
        if chat_id in chat_service.active_chats and "files" in chat_service.active_chats[chat_id]:
            # 获取最后添加的文件
            files = chat_service.active_chats[chat_id]["files"]
            if files:
                latest_file = files[-1]
                # 为文件生成一个ID
                file_id = str(uuid.uuid4())
                latest_file["id"] = file_id
                
                # 返回文件信息，包括ID
                return {
                    "id": file_id,
                    "name": file.filename,
                    "size": len(file_content),
                    "upload_time": datetime.now().isoformat()
                }
        
        # 如果无法获取文件信息，返回基本成功消息
        return {
            "id": str(uuid.uuid4()),
            "name": file.filename,
            "size": len(file_content),
            "upload_time": datetime.now().isoformat(),
            "message": "PDF file processed successfully"
        }
    
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
                    # Get file path for later deletion
                    file_path = file_data["file_path"]
                    file_name = file_data.get("filename", "document.pdf")
                    
                    # Remove from the session's files list
                    chat_service.active_chats[chat_id]["files"].pop(idx)
                    
                    # Delete the file if it exists
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.error(f"Error deleting file {file_path}: {str(e)}")
                    
                    return {"message": f"File {file_name} deleted successfully"}
    
    # If file not found
    raise HTTPException(
        status_code=404,
        detail=f"File with ID {file_id} not found"
    ) 