from fastapi import APIRouter, HTTPException, Body, Path, Request, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import logging
import json

from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatResponseChunk:
    """
    Stream response chunk
    """
    def __init__(self, content: str, done: bool = False):
        self.content = content
        self.done = done
    
    def to_json(self) -> str:
        """
        change response chunk to json string
        """
        return json.dumps({
            "content": self.content,
            "done": self.done
        }, ensure_ascii=False)


@router.get("/messages")
async def get_chat_messages(
    request: Request,
):
    """
    Get user's history messages
    """
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found"
        )
    messages = []
    messages = chat_service.get_messages(user_id)
    return messages


@router.post("/stream_chat")
async def chat(
    request: Request,
    message: str = Body(embed=True)
):
    """
    get stream chat response
    """
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found"
        )

    if user_id not in chat_service.active_chats:
        chat_service.active_chats[user_id] = {
            "messages": [],
            "files": []
        }
    
    async def stream_chat_response():
        try:
            async for content_chunk, is_done in chat_service.generate_response(user_id, message):
                response_chunk = ChatResponseChunk(content=content_chunk, done=is_done)
                json_chunk = response_chunk.to_json() + "\n"
                yield json_chunk
        except Exception as e:
            logger.error(f"Error in stream_chat_response: {str(e)}")
            error_chunk = ChatResponseChunk(content="Error processing request", done=True)
            yield error_chunk.to_json() + "\n"
    
    return StreamingResponse(
        stream_chat_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" 
        }
    )


@router.get("/files")
async def get_user_files(
    request: Request
):
    """
    Get user's attached files
    """
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found"
        )
    
    if user_id not in chat_service.active_chats:
        chat_service.active_chats[user_id] = {
            "messages": [],
            "files": []
        }
    
    chat_data = chat_service.active_chats[user_id]
    result = []

    if chat_data["files"]:
        for file_data in chat_data["files"]:
            result.append({
                "file_path": file_data["file_path"],
                "filename": file_data["filename"],
                "paper_id": file_data["paper_id"],
                "paper_URL": file_data["paper_URL"],
                "added_at": file_data["added_at"]
            })
    
    return result


@router.delete("/files/delete/{paper_id}")
async def delete_file(
    request: Request,
    paper_id: str = Path()
):
    """
    Delete a file from user's attached files
    """
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found"
        )
    
    chat_data = chat_service.active_chats[user_id]
    
    if chat_data["files"]:
        for file_data in chat_data["files"]:
            if file_data["paper_id"] == paper_id:
                chat_data["files"].remove(file_data)
                return True
    
    return False


@router.post("/attach_paper")
async def attach_paper(
    request: Request,
    paper_id: str = Body(embed=True)
):
    """
    Attach a paper to user, download the paper if not exists
    """
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(    
            status_code=401,
            detail="User ID not found"
        )
    try:
        success = await chat_service.attach_paper(user_id, paper_id)
        
        if not success:
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"Error attaching paper {paper_id} to chat session {user_id}: {str(e)}")
        return False


@router.post("/process_embeddings")
async def process_paper_embeddings(
    request: Request,
    paper_id: str = Body(embed=True)
):
    """
    Process embeddings for a paper
    """

    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID not found"
        )
    
    try:
        success = await chat_service.process_embeddings(paper_id)
        
        if not success:
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"Error processing embeddings for paper {paper_id} for user {user_id}: {str(e)}")
        return False