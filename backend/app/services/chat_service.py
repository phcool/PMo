import os
import logging
import json
import time
import uuid
import asyncio
import aiofiles
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple

from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
from app.services.db_service import db_service
# Paper model不再需要导入，因为我们简化了聊天功能，移除了特定研究论文的元数据处理

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat conversations, including RAG with PDFs."""
    
    def __init__(self):
        """Initialize chat service"""
        # 设置配置
        self.max_context_messages = int(os.getenv("CHAT_MAX_CONTEXT", "10"))
        self.max_chunks_per_query = int(os.getenv("CHAT_MAX_CHUNKS", "5"))
        self.session_timeout_hours = float(os.getenv("CHAT_SESSION_TIMEOUT", "0.5"))
        
        # 存储活跃会话
        self.active_chats = {}
        
        # 跟踪PDF处理状态
        self.processing_files = {}
        
        # 启动会话清理任务
        asyncio.create_task(self._start_session_cleanup_task())
        
        logger.info(f"Chat Service initialized. Max context: {self.max_context_messages}, Max chunks: {self.max_chunks_per_query}")
    
    def create_chat_session(self, paper_id: Optional[str] = None) -> str:
        """创建新的聊天会话"""
        chat_id = str(uuid.uuid4())
        
        self.active_chats[chat_id] = {
            "paper_id": paper_id,
            "file_path": None,
            "messages": [],
            "last_activity": time.time()
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
                await asyncio.sleep(1800)
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
        """向聊天会话添加消息"""
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
        """获取聊天会话中的消息"""
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
        """检查指定会话是否正在处理文件"""
        # 更新会话活动时间（仅当会话存在时）
        if chat_id in self.active_chats:
            self._update_session_activity(chat_id)
            
        if chat_id not in self.processing_files:
            return {"processing": False, "file_name": ""}
        return self.processing_files[chat_id]
    
    async def process_paper(self, chat_id: str, paper_id: str) -> bool:
        """处理论文PDF并关联到聊天会话"""
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return False
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
        
        try:
            # 标记为处理中
            filename = f"{paper_id}.pdf"
            self.processing_files[chat_id] = {"processing": True, "file_name": filename}
            
            # 获取论文数据，用于日志记录和生成友好的文件名
            paper = await db_service.get_paper_by_id(paper_id)
            paper_title = paper.title if paper else None
            logger.info(f"Processing paper {paper_id}: {paper_title or 'Unknown title'}")
            
            # 从OSS获取PDF
            logger.info(f"Requesting PDF from OSS for paper_id: {paper_id}")
            file_path = await pdf_service.get_pdf_from_oss(paper_id)
            
            if not file_path:
                logger.error(f"Failed to get PDF for paper: {paper_id} - returned empty file path")
                self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                return False
            
            # 验证文件是否实际存在
            if not os.path.exists(file_path):
                logger.error(f"PDF file path returned but file does not exist: {file_path}")
                self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                return False
                
            logger.info(f"Successfully obtained PDF file at: {file_path}")
            
            # 更新聊天会话的文件列表，使用论文标题作为文件名
            update_result = await pdf_service.update_chat_files(chat_id, file_path, paper_id, paper_title)
            
            if not update_result["success"]:
                logger.error(f"Failed to update chat files: {update_result.get('error', 'Unknown error')}")
                self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                return False
                
            # 如果文件已存在于会话中，检查是否需要处理
            if update_result.get("already_exists"):
                logger.info(f"Paper {paper_id} already exists in chat session {chat_id}, checking if processing is needed")
                
                # 获取文件的数量信息
                files_count = len(self.active_chats[chat_id].get("files", []))
                
                # 论文已经关联到此会话并处理过，无需再次处理
                logger.info(f"Paper {paper_id} already processed for this chat session, skipping processing")
                return True
            
            # 为PDF创建向量存储
            logger.info(f"Creating vector store for file: {file_path}")
            success = await pdf_service.create_vector_store(file_path, chat_id)
            logger.info(f"Vector store creation result: {'success' if success else 'failed'}")
            
            # 更新处理状态
            if success:
                # 获取当前会话中的文件总数
                files_count = len(self.active_chats[chat_id].get("files", []))
                
                # 更新处理状态，包含文件数量信息
                self.processing_files[chat_id] = {
                    "processing": False, 
                    "file_name": update_result["file_info"].get("filename", filename),
                    "files_count": files_count
                }
                
                # 添加系统消息表示论文已加载
                if paper:
                    paper_title = paper.title
                    self.add_message(
                        chat_id,
                        "system",
                        f"Paper loaded: '{paper_title}' (ID: {paper_id}). You can now ask questions about this paper."
                    )
                    logger.info(f"Added system message about loaded paper '{paper_title}'")
                
                logger.info(f"Successfully processed PDF for paper {paper_id} in chat session {chat_id}. Total files: {files_count}")
                return True
            else:
                # 如果处理失败，也标记为处理完成
                self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                logger.error(f"Failed to process PDF for paper {paper_id} in chat session {chat_id}")
                return False
                
        except Exception as e:
            # 发生异常时，标记为处理完成
            self.processing_files[chat_id] = {"processing": False, "file_name": filename}
            logger.error(f"Error processing paper {paper_id} for chat session {chat_id}: {str(e)}", exc_info=True)
            return False
    
    async def end_chat_session(self, chat_id: str) -> bool:
        """结束聊天会话并清理关联资源"""
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
            
            # 清理会话向量存储
            pdf_service.cleanup_session(chat_id)
            
            # 从活跃会话中移除
            del self.active_chats[chat_id]
            
            # 清理处理状态
            if chat_id in self.processing_files:
                del self.processing_files[chat_id]
                
            logger.info(f"Ended chat session: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error ending chat session {chat_id}: {str(e)}")
            return False
    
    async def _format_messages_for_api(self, chat_id: str) -> List[Dict[str, str]]:
        """为API调用格式化消息，包括系统提示词"""
        chat_data = self.active_chats.get(chat_id)
        if not chat_data:
            logger.error(f"Chat session not found: {chat_id}")
            return []
        
        # 从系统提示词开始
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
        
        # 对于基于PDF的聊天，添加使用上下文的指示
        if has_uploaded_pdfs:
            if len(uploaded_filenames) == 1:
                system_content += "\nYou have been provided with relevant context from the uploaded PDF document. Use this context to answer questions specifically and accurately."
            else:
                system_content += f"\nYou have been provided with relevant context from {len(uploaded_filenames)} uploaded PDF documents: {', '.join(uploaded_filenames)}. When answering questions, use the most relevant information from any of these documents."
        else:
            system_content += "\nNo PDF has been uploaded yet. You should encourage the user to upload a PDF to get detailed answers to their questions."
        
        # 为API格式化消息，从系统消息开始
        api_messages = [{"role": "system", "content": system_content}]
        
        # 添加聊天历史（限制为max_context_messages）
        user_messages = [m for m in chat_data["messages"] if m["role"] in ["user", "assistant"]]
        recent_messages = user_messages[-self.max_context_messages:]
        
        for msg in recent_messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return api_messages
    
    async def generate_response(self, chat_id: str, query: str) -> AsyncGenerator[Tuple[str, bool], None]:
        """生成对用户查询的响应，如果有PDF附件则使用RAG"""
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            yield "Sorry, your chat session was not found.", True
            return
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
        
        # 添加用户消息到历史记录
        self.add_message(chat_id, "user", query)
        
        # 检查会话是否有上传文件
        chat_data = self.active_chats[chat_id]
        has_uploaded_pdfs = "files" in chat_data and chat_data["files"] or chat_data.get("file_path")
        
        # 如果有PDF，使用RAG
        if has_uploaded_pdfs:
            try:
                # 从PDF中获取相关的文本块
                relevant_chunks = await pdf_service.query_similar_chunks(
                    chat_id, 
                    query,
                    top_k=self.max_chunks_per_query
                )
                
                # 使用检索的上下文格式化消息
                api_messages = await self._format_messages_for_api(chat_id)
                
                # 将检索的上下文添加到最后一条用户消息
                if relevant_chunks:
                    context_text = "\n\n".join(relevant_chunks)
                    last_message_idx = len(api_messages) - 1
                    
                    # 创建一个包含上下文的新消息
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
                # 如果RAG失败，回退到常规消息格式
                api_messages = await self._format_messages_for_api(chat_id)
        else:
            # 常规消息格式（无RAG）
            api_messages = await self._format_messages_for_api(chat_id)
        
        # 从LLM生成响应
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

# 实例化单例
chat_service = ChatService() 