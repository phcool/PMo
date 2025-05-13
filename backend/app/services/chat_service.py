import os
import logging
import json
import time
import uuid
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple

from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
# Paper model不再需要导入，因为我们简化了聊天功能，移除了特定研究论文的元数据处理

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat conversations, including RAG with PDFs."""
    
    def __init__(self):
        """Initialize chat service"""
        # Set up configuration
        self.max_context_messages = int(os.getenv("CHAT_MAX_CONTEXT", "10"))  # Max messages to include in context
        self.max_chunks_per_query = int(os.getenv("CHAT_MAX_CHUNKS", "5"))  # Max number of chunks to retrieve for RAG
        self.session_timeout_hours = float(os.getenv("CHAT_SESSION_TIMEOUT", "0.5"))  # 会话超时时间（小时），默认30分钟
        
        # Stores active chats: {"chat_id": {"paper_id": str, "file_path": str, "messages": List[Dict], "last_activity": float}}
        self.active_chats = {}
        
        # 跟踪PDF处理状态: {"chat_id": {"processing": bool, "file_name": str}}
        self.processing_files = {}
        
        # 启动会话清理任务
        asyncio.create_task(self._start_session_cleanup_task())
        
        logger.info(f"Chat Service initialized. Max context: {self.max_context_messages}, Max chunks: {self.max_chunks_per_query}, Session timeout: {self.session_timeout_hours}h")
    
    def create_chat_session(self, paper_id: Optional[str] = None) -> str:
        """
        Create a new chat session
        
        Args:
            paper_id: Optional paper ID if chat is about a specific paper
                     (仍然保留此参数以保持兼容性，但不再提供论文元数据给模型)
            
        Returns:
            Chat session ID
        """
        chat_id = str(uuid.uuid4())
        
        self.active_chats[chat_id] = {
            "paper_id": paper_id,
            "file_path": None,
            "messages": [],
            "last_activity": time.time()  # 记录创建时间
        }
        
        logger.info(f"Created new chat session {chat_id}" + (f" for paper {paper_id}" if paper_id else ""))
        return chat_id
    
    def _update_session_activity(self, chat_id: str):
        """更新会话最后活动时间"""
        if chat_id in self.active_chats:
            self.active_chats[chat_id]["last_activity"] = time.time()
    
    async def _start_session_cleanup_task(self):
        """启动定期清理过期会话的任务"""
        while True:
            try:
                # 每30分钟运行一次清理
                await asyncio.sleep(1800)  # 1800秒 = 30分钟
                await self._cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in session cleanup task: {str(e)}")
    
    async def _cleanup_expired_sessions(self):
        """清理过期的聊天会话"""
        logger.info("Starting scheduled cleanup of expired chat sessions")
        current_time = time.time()
        expiry_seconds = self.session_timeout_hours * 3600
        
        # 识别长时间未活跃的会话
        expired_sessions = []
        for chat_id, data in list(self.active_chats.items()):
            last_activity = data.get("last_activity", 0)
            if current_time - last_activity > expiry_seconds:
                expired_sessions.append(chat_id)
        
        # 结束过期会话
        for chat_id in expired_sessions:
            logger.info(f"Auto-ending expired chat session: {chat_id}")
            try:
                await self.end_chat_session(chat_id)
            except Exception as e:
                logger.error(f"Error ending expired session {chat_id}: {str(e)}")
        
        logger.info(f"Session cleanup completed. Ended {len(expired_sessions)} expired sessions.")
    
    def add_message(self, chat_id: str, role: str, content: str):
        """
        Add a message to a chat session
        
        Args:
            chat_id: Chat session ID
            role: Message role (user/assistant/system)
            content: Message content
        """
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return
        
        self.active_chats[chat_id]["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
    
    def get_messages(self, chat_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get messages from a chat session
        
        Args:
            chat_id: Chat session ID
            limit: Maximum number of messages to return (most recent)
            
        Returns:
            List of messages
        """
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return []
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
        
        messages = self.active_chats[chat_id]["messages"]
        
        if limit:
            return messages[-limit:]
        return messages
    
    def is_processing_file(self, chat_id: str) -> Dict[str, Any]:
        """
        检查指定会话是否正在处理文件
        
        Args:
            chat_id: 聊天会话ID
            
        Returns:
            包含处理状态的字典: {"processing": bool, "file_name": str}
        """
        # 更新会话活动时间（仅当会话存在时）
        if chat_id in self.active_chats:
            self._update_session_activity(chat_id)
            
        if chat_id not in self.processing_files:
            return {"processing": False, "file_name": ""}
        return self.processing_files[chat_id]
        
    async def process_pdf(self, chat_id: str, file_content: bytes, filename: str) -> bool:
        """
        Process an uploaded PDF for a chat session
        
        Args:
            chat_id: Chat session ID
            file_content: PDF file content
            filename: Original filename
            
        Returns:
            True if successful, False otherwise
        """
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return False
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
        
        try:
            # 标记为处理中
            self.processing_files[chat_id] = {"processing": True, "file_name": filename}
            
            # Save the uploaded PDF
            file_path = await pdf_service.save_uploaded_pdf(file_content, filename)
            
            # 检查是否是该会话的第一个PDF
            is_first_pdf = "files" not in self.active_chats[chat_id]
            
            # 初始化文件列表（如果不存在）
            if is_first_pdf:
                self.active_chats[chat_id]["files"] = []
                
            # 添加当前文件到文件列表
            self.active_chats[chat_id]["files"].append({
                "file_path": file_path,
                "filename": filename
            })
            
            # 更新当前活跃文件路径（总是使用最新上传的文件作为当前活跃文件）
            self.active_chats[chat_id]["file_path"] = file_path
            
            # Create vector store for the PDF
            success = await pdf_service.create_vector_store(file_path, chat_id)
            
            # 更新处理状态
            if success:
                # 获取当前会话中的文件总数
                files_count = len(self.active_chats[chat_id].get("files", []))
                
                # 更新处理状态，包含文件数量信息
                self.processing_files[chat_id] = {
                    "processing": False, 
                    "file_name": filename,
                    "files_count": files_count
                }
                
                logger.info(f"Successfully processed PDF for chat session {chat_id}. Total files: {files_count}")
                return True
            else:
                # 如果处理失败，也标记为处理完成
                self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                logger.error(f"Failed to process PDF for chat session {chat_id}")
                return False
                
        except Exception as e:
            # 发生异常时，标记为处理完成
            self.processing_files[chat_id] = {"processing": False, "file_name": filename}
            logger.error(f"Error processing PDF for chat session {chat_id}: {str(e)}")
            return False
    
    async def end_chat_session(self, chat_id: str) -> bool:
        """
        End a chat session and clean up associated resources
        
        Args:
            chat_id: Chat session ID
            
        Returns:
            True if session was successfully ended, False otherwise
        """
        if chat_id not in self.active_chats:
            logger.warning(f"Attempted to end non-existent chat session: {chat_id}")
            return False
            
        try:
            # 检查会话是否有多个文件
            chat_data = self.active_chats[chat_id]
            if "files" in chat_data and chat_data["files"]:
                # 记录会话中的所有文件路径，以便后续清理
                for file_data in chat_data["files"]:
                    file_path = file_data.get("file_path")
                    if file_path:
                        logger.info(f"File {file_path} will be cleaned up by expiry")
            else:
                # 兼容旧逻辑 - 如果没有使用files数组
                file_path = chat_data.get("file_path")
                if file_path:
                    logger.info(f"File {file_path} will be cleaned up by expiry")
            
            # Clean up session vectors if they exist
            pdf_service.cleanup_session(chat_id)
            
            # Remove from active chats
            del self.active_chats[chat_id]
            
            # Clear processing status if exists
            if chat_id in self.processing_files:
                del self.processing_files[chat_id]
                
            logger.info(f"Ended chat session: {chat_id}")
            
            # Note: We don't automatically delete the uploaded PDF files
            # The PDF service's cleanup task will handle this based on expiry time
            
            return True
        except Exception as e:
            logger.error(f"Error ending chat session {chat_id}: {str(e)}")
            return False
    
    async def _format_messages_for_api(self, chat_id: str) -> List[Dict[str, str]]:
        """
        Format messages for the LLM API call, including system prompt
        
        Args:
            chat_id: Chat session ID
            
        Returns:
            List of formatted messages for API
            
        Note:
            此方法已简化，移除了paper元数据相关功能。现在使用通用的助手提示词，
            不再针对研究论文提供特定的元数据上下文。
        """
        chat_data = self.active_chats.get(chat_id)
        if not chat_data:
            logger.error(f"Chat session not found: {chat_id}")
            return []
        
        # Start with a system prompt
        system_content = "You are a helpful assistant that provides accurate, concise and thoughtful responses to user questions."
        
        # 检查会话是否有多个文件
        has_uploaded_pdfs = False
        uploaded_filenames = []
        
        # 收集所有已上传的文件信息
        if "files" in chat_data and chat_data["files"]:
            has_uploaded_pdfs = True
            for file_data in chat_data["files"]:
                uploaded_filenames.append(file_data.get("filename", "Unknown file"))
        elif chat_data.get("file_path"):
            # 兼容旧版本的单文件逻辑
            has_uploaded_pdfs = True
        
        # For PDF-based chat, add instructions for using context
        if has_uploaded_pdfs:
            if len(uploaded_filenames) == 1:
                system_content += "\nYou have been provided with relevant context from the uploaded PDF document. Use this context to answer questions specifically and accurately. If the answer cannot be fully found in the provided context, say so clearly."
            else:
                system_content += f"\nYou have been provided with relevant context from {len(uploaded_filenames)} uploaded PDF documents: {', '.join(uploaded_filenames)}. When answering questions, use the most relevant information from any of these documents. If asked about a specific document, focus on that one. If the answer cannot be fully found in the provided context, say so clearly."
        else:
            system_content += "\nNo PDF has been uploaded yet. You should encourage the user to upload a PDF to get detailed answers to their questions."
        
        # Format messages for API, starting with system message
        api_messages = [{"role": "system", "content": system_content}]
        
        # Add chat history (limit to max_context_messages)
        user_messages = [m for m in chat_data["messages"] if m["role"] in ["user", "assistant"]]
        recent_messages = user_messages[-self.max_context_messages:]
        
        for msg in recent_messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return api_messages
    
    async def generate_response(self, chat_id: str, query: str) -> AsyncGenerator[Tuple[str, bool], None]:
        """
        Generate a response to a user query, with RAG if a PDF is attached
        
        Args:
            chat_id: Chat session ID
            query: User query
            
        Returns:
            AsyncGenerator that yields (content_chunk, is_done) tuples
            
        Note:
            此方法已简化，移除了paper参数，不再处理特定研究论文的元数据。
            现在仅支持通用的PDF文档提问，而不区分是否为研究论文。
        """
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            yield "Sorry, your chat session was not found.", True
            return
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
        
        # Add user message to chat history
        self.add_message(chat_id, "user", query)
        
        # 检查会话是否有上传文件
        chat_data = self.active_chats[chat_id]
        has_uploaded_pdfs = "files" in chat_data and chat_data["files"] or chat_data.get("file_path")
        
        # If there's a PDF, use RAG
        if has_uploaded_pdfs:
            try:
                # Retrieve relevant chunks from the PDFs
                relevant_chunks = await pdf_service.query_similar_chunks(
                    chat_id, 
                    query, 
                    top_k=self.max_chunks_per_query
                )
                
                # Format messages with the retrieved context
                api_messages = await self._format_messages_for_api(chat_id)
                
                # Add the retrieved context to the last user message
                if relevant_chunks:
                    context_text = "\n\n".join(relevant_chunks)
                    last_message_idx = len(api_messages) - 1
                    
                    # Create a new message with context
                    enhanced_query = f"""
                    {query}
                    
                    Here is some relevant content from the PDFs:
                    ---
                    {context_text}
                    ---
                    """
                    
                    api_messages[last_message_idx]["content"] = enhanced_query
            except Exception as e:
                logger.error(f"Error performing RAG for chat {chat_id}: {str(e)}")
                # Fall back to regular message formatting without RAG
                api_messages = await self._format_messages_for_api(chat_id)
        else:
            # Regular message formatting without RAG
            api_messages = await self._format_messages_for_api(chat_id)
        
        # Generate response from LLM
        assistant_response = ""
        try:
            # 直接使用llm_service的流式响应
            stream_response = await llm_service.get_conversation_completion(
                messages=api_messages,
                temperature=llm_service.conversation_temperature,
                max_tokens=llm_service.max_tokens
            )
            
            if not stream_response:
                error_msg = "Sorry, I couldn't generate a response at this time."
                self.add_message(chat_id, "assistant", error_msg)
                yield error_msg, True
                return
            
            # 处理流式响应的每个块
            async for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    assistant_response += content
                    # 立即发送每个token
                    yield content, False
            
            # 完成后添加到聊天历史
            if assistant_response:
                self.add_message(chat_id, "assistant", assistant_response)
                
            # 发送结束标志
            yield "", True
                
        except Exception as e:
            logger.error(f"Error generating response for chat {chat_id}: {str(e)}")
            error_msg = "Sorry, I encountered an error while processing your request."
            self.add_message(chat_id, "assistant", error_msg)
            yield error_msg, True

# Instantiate a singleton
chat_service = ChatService() 