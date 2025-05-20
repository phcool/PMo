import os
import logging
import json
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
import re
from pathlib import Path

from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
from app.services.db_service import db_service
from app.services.oss_service import oss_service

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat conversations, including RAG with PDFs."""
    
    def __init__(self):
        """Initialize chat service"""
        # 设置配置
        self.max_context_messages = int(os.getenv("CHAT_MAX_CONTEXT", "10"))
        self.max_chunks_per_query = int(os.getenv("CHAT_MAX_CHUNKS", "30"))
        
        # 存储活跃会话
        self.active_chats = {}
        
        # 跟踪PDF处理状态
        self.processing_files = {}
        
        logger.info(f"Chat Service initialized. Max context: {self.max_context_messages}, Max chunks: {self.max_chunks_per_query}")
    
    def create_chat_session(self) -> str:
        """创建新的聊天会话"""
        chat_id = str(uuid.uuid4())
        
        self.active_chats[chat_id] = {
            "messages": [],
            "files": []
        }
        
        logger.info(f"Created new chat session {chat_id}")
        return chat_id
    
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
    
    def get_messages(self, chat_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """获取聊天会话中的消息"""
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return []
        
        messages = self.active_chats[chat_id]["messages"]
        
        if limit:
            return messages[-limit:]
        return messages
    
    def is_processing_file(self, chat_id: str) -> Dict[str, Any]:
        """检查指定会话是否正在处理文件"""
        if chat_id not in self.processing_files:
            return {"processing": False, "file_name": ""}
        return self.processing_files[chat_id]
    
    async def get_paper_pdf(self, chat_id: str, paper_id: str) -> bool:
        """获取论文PDF并关联到聊天会话，但不进行向量化处理"""
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return False
        
        try:
            # 标记为处理中
            filename = f"{paper_id}.pdf"
            self.processing_files[chat_id] = {"processing": True, "file_name": filename}
            
            # 获取论文数据，用于日志记录和生成友好的文件名
            paper = await db_service.get_paper_by_id(paper_id)
            paper_title = paper.title if paper else None
            logger.info(f"Getting PDF for paper {paper_id}: {paper_title or 'Unknown title'}")
            
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
            
            logger.info(f"Successfully added PDF for paper {paper_id} to chat session {chat_id}. Total files: {files_count}")
            return True
                
        except Exception as e:
            # 发生异常时，标记为处理完成
            self.processing_files[chat_id] = {"processing": False, "file_name": filename}
            logger.error(f"Error getting PDF for paper {paper_id} for chat session {chat_id}: {str(e)}", exc_info=True)
            return False

    async def process_paper_embeddings(self, chat_id: str, paper_id: str) -> bool:
        """为已加载的PDF创建向量存储，优先本地缓存，再查OSS，OSS拉取后也缓存本地，如果都没有则从PDF生成"""
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return False
        try:
            filename = f"{paper_id}.pdf"
            self.processing_files[chat_id] = {"processing": True, "file_name": filename}

            # 1. 解析年份和月份，确定本地路径
            match = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
            if not match:
                logger.error(f"Invalid paper_id format: {paper_id}")
                self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                return False
            year, month, _ = match.groups()
            local_dir = Path("cached_embeddings") / year / month
            local_dir.mkdir(parents=True, exist_ok=True)
            local_path = local_dir / f"{paper_id.replace('.', '_')}.json"

            # 2. 检查本地是否已存在 embedding 文件
            if local_path.exists():
                logger.info(f"Found local embedding file: {local_path}")
            else:
                # 3. 本地没有则从 OSS 拉取
                logger.info(f"Local embedding not found, downloading from OSS for paper_id: {paper_id}")
                chunks, embeddings = await oss_service.get_vector_embeddings(paper_id)
                
                if not chunks or not embeddings:
                    # 4. OSS也没有，需要从PDF生成
                    logger.info(f"No embeddings found in OSS, generating from PDF for paper_id: {paper_id}")
                    
                    # 获取会话中的文件信息
                    session = self.active_chats[chat_id]
                    files = session.get("files", [])
                    file_info = next((f for f in files if f.get("paper_id") == paper_id), None)
                    
                    if not file_info or not file_info.get("file_path"):
                        logger.error(f"No PDF file found for paper_id: {paper_id}")
                        self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                        return False
                    
                    # 使用pdf_service生成embeddings（会自动保存到本地和OSS）
                    chunks, embeddings, _ = await pdf_service.generate_embeddings_for_paper(
                        paper_id=paper_id,
                        file_path=file_info["file_path"]
                    )
                    
                    if not chunks or not embeddings:
                        logger.error(f"Failed to generate embeddings for paper_id: {paper_id}")
                        self.processing_files[chat_id] = {"processing": False, "file_name": filename}
                        return False
                else:
                    # OSS获取成功，保存到本地
                    with open(local_path, 'w', encoding='utf-8') as f:
                        json.dump({"chunks": chunks, "embeddings": embeddings}, f)
                    logger.info(f"Downloaded and cached embedding to {local_path}")

            # 5. embedding 文件已缓存到本地，更新处理状态
            files_count = len(self.active_chats[chat_id].get("files", []))
            self.processing_files[chat_id] = {
                "processing": False,
                "file_name": filename,
                "files_count": files_count
            }
            logger.info(f"Successfully processed embeddings for paper {paper_id} in chat session {chat_id}")
            return True
        except Exception as e:
            self.processing_files[chat_id] = {"processing": False, "file_name": filename}
            logger.error(f"Error processing embeddings for paper {paper_id} for chat session {chat_id}: {str(e)}", exc_info=True)
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
                        logger.info(f"File {file_path} will be cleaned up")
            
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
        """Format messages for API call, including system prompt (in English, always answer user even if no PDF)"""
        chat_data = self.active_chats.get(chat_id)
        if not chat_data:
            logger.error(f"Chat session not found: {chat_id}")
            return []
        
        has_uploaded_pdfs = False
        uploaded_filenames = []
        if "files" in chat_data and chat_data["files"]:
            has_uploaded_pdfs = True
            for file_data in chat_data["files"]:
                uploaded_filenames.append(file_data.get("filename", "Unknown file"))
        
        if has_uploaded_pdfs:
            system_content = (
                "You are a professional academic paper analysis assistant. You can analyze papers and answer questions based on the uploaded PDF papers. "
                f"There are {len(uploaded_filenames)} PDF(s) uploaded in this session: {', '.join(uploaded_filenames)}. Please cite specific content from the papers to help the user understand them deeply."
            )
        else:
            system_content = (
                "You are a professional academic paper analysis assistant. Please answer the user's question as best as you can. If the user uploads a PDF, you can provide more detailed and accurate analysis based on the paper content."
            )
        
        api_messages = [{"role": "system", "content": system_content}]
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
        
        # 添加用户消息到历史记录
        self.add_message(chat_id, "user", query)
        
        # 检查会话是否有上传文件
        chat_data = self.active_chats[chat_id]
        has_uploaded_pdfs = "files" in chat_data and chat_data["files"]
        
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