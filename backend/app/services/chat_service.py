import os
import logging
import json
import time
import uuid
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple

from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
from app.services.vector_search_service import vector_search_service
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
        
    async def process_pdf(self, chat_id: str, file_content: bytes, filename: str) -> bool:
        """处理上传的PDF文件"""
        if chat_id not in self.active_chats:
            logger.error(f"Chat session not found: {chat_id}")
            return False
        
        # 更新会话活动时间
        self._update_session_activity(chat_id)
        
        try:
            # 标记为处理中
            self.processing_files[chat_id] = {"processing": True, "file_name": filename}
            
            # 保存上传的PDF
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
            
            # 更新当前活跃文件路径
            self.active_chats[chat_id]["file_path"] = file_path
            
            # 为PDF创建向量存储
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
        
        # 检查是否是搜索模式查询
        is_search_mode = query.startswith("[SEARCH]")
        
        # 如果是搜索模式，去掉[SEARCH]前缀
        if is_search_mode:
            original_query = query[8:].strip()  # 去掉[SEARCH]和可能的空格
            # A保存未修改的用户查询到历史记录
            self.add_message(chat_id, "user", original_query)
            logger.info(f"SEARCH MODE: Chat {chat_id} using search mode with query: '{original_query}'")
        else:
            # 常规查询，直接添加到历史记录
            self.add_message(chat_id, "user", query)
            original_query = query
        
        # 检查会话是否有上传文件
        chat_data = self.active_chats[chat_id]
        has_uploaded_pdfs = "files" in chat_data and chat_data["files"] or chat_data.get("file_path")
        
        # 使用vector_search_service获取相关论文元数据（仅搜索模式）
        paper_metadata = ""
        if is_search_mode:
            try:
                # 获取与查询相关的前5篇论文ID
                paper_ids = await vector_search_service.search(original_query, k=5)
                
                if paper_ids:
                    # 获取论文详细信息
                    related_papers = []
                    for paper_id in paper_ids:
                        paper = await db_service.get_paper_by_id(paper_id)
                        if paper:
                            related_papers.append(paper)
                    
                    # 构建论文元数据文本
                    if related_papers:
                        paper_metadata = "You MUST analyze the following specific papers from my search results:\n\n"
                        for i, paper in enumerate(related_papers, 1):
                            # 构建论文元数据，仅保留必要信息给AI
                            paper_metadata += f"Paper {i}: \"{paper.title}\"\n"
                            paper_metadata += f"Authors: {', '.join(paper.authors)}\n"
                            paper_metadata += f"Categories: {', '.join(paper.categories)}\n"
                            if paper.abstract:
                                # 限制摘要长度，最多显示500个字符
                                abstract = paper.abstract[:500]
                                if len(paper.abstract) > 500:
                                    abstract += "..."
                                paper_metadata += f"Abstract: {abstract}\n"
                            paper_metadata += "\n"
                        
                        logger.info(f"Found {len(related_papers)} related papers for search query: '{original_query}'")
                    else:
                        logger.info(f"No related papers found for search query: '{original_query}'")
            except Exception as e:
                logger.error(f"Error searching for related papers: {str(e)}")
        
        # 如果有PDF，使用RAG
        if has_uploaded_pdfs:
            try:
                # 从PDF中获取相关的文本块
                relevant_chunks = await pdf_service.query_similar_chunks(
                    chat_id, 
                    original_query,
                    top_k=self.max_chunks_per_query
                )
                
                # 使用检索的上下文格式化消息
                api_messages = await self._format_messages_for_api(chat_id)
                
                # 将检索的上下文添加到最后一条用户消息
                if relevant_chunks:
                    context_text = "\n\n".join(relevant_chunks)
                    last_message_idx = len(api_messages) - 1
                    
                    # 创建一个包含上下文的新消息
                    if is_search_mode:
                        # 搜索模式下添加更多指导，包括论文元数据
                        enhanced_query = f"""
                        {original_query}
                        
                        When analyzing these papers:
                        1. Begin by stating "Based on my search, I found several relevant papers that address your query."
                        2. You MUST analyze EACH of the specific papers provided below, individually and in detail:
                           - For EACH paper, start with "Paper X: [Title]" as a heading (where X is the number and [Title] is the exact paper title)
                           - Summarize its key methods and findings
                           - Explain specifically how it relates to the query
                           - Highlight any notable strengths or limitations
                        3. After analyzing each paper individually, identify any contradictions or complementary information between them
                        4. Conclude with a synthesis of the key insights
                        
                        IMPORTANT: Only analyze the specific papers provided in this prompt. The paper data is already displayed to the user.
                        
                        {paper_metadata}
                        
                        Here is also some relevant content from the PDFs you've uploaded:
                        ---
                        {context_text}
                        ---
                        """
                    else:
                        # 常规对话模式
                        enhanced_query = f"""
                        {original_query}
                        
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
                
                # 如果是搜索模式，添加论文元数据到最后一条用户消息
                if is_search_mode and paper_metadata and len(api_messages) > 0:
                    last_message_idx = len(api_messages) - 1
                    api_messages[last_message_idx]["content"] = f"""
                    {original_query}
                    
                    When analyzing these papers:
                    1. Begin by stating "Based on my search, I found several relevant papers that address your query."
                    2. You MUST analyze EACH of the specific papers provided below, individually and in detail:
                       - For EACH paper, start with "Paper X: [Title]" as a heading (where X is the number and [Title] is the exact paper title)
                       - Summarize its key methods and findings
                       - Explain specifically how it relates to the query
                       - Highlight any notable strengths or limitations
                    3. After analyzing each paper individually, identify any contradictions or complementary information between them
                    4. Conclude with a synthesis of the key insights
                    
                    IMPORTANT: Only analyze the specific papers provided in this prompt. The paper data is already displayed to the user.
                    
                    {paper_metadata}
                    """
        else:
            # 常规消息格式（无RAG）
            api_messages = await self._format_messages_for_api(chat_id)
            
            # 如果是搜索模式添加特殊指导和论文元数据
            if is_search_mode:
                last_message_idx = len(api_messages) - 1
                
                # 构建带有论文元数据的搜索提示词
                search_prompt = f"""
                {original_query}
                
                When analyzing these papers:
                1. Begin by stating "Based on my search, I found several relevant papers that address your query."
                2. You MUST analyze EACH of the specific papers provided below, individually and in detail:
                   - For EACH paper, start with "Paper X: [Title]" as a heading (where X is the number and [Title] is the exact paper title)
                   - Summarize its key methods and findings
                   - Explain specifically how it relates to the query
                   - Highlight any notable strengths or limitations
                3. After analyzing each paper individually, identify any contradictions or complementary information between them
                4. Conclude with a synthesis of the key insights

                IMPORTANT: Only analyze the specific papers provided in this prompt. The paper data is already displayed to the user.
                """
                
                # 强制添加paper_metadata，确保AI分析这些特定论文
                if paper_metadata:
                    search_prompt += f"\n\n{paper_metadata}"
                
                api_messages[last_message_idx]["content"] = search_prompt
        
        # 从LLM生成响应
        assistant_response = ""
        try:
            # 如果是搜索模式且找到了论文，首先发送论文数据
            if is_search_mode and related_papers:
                # 构建论文数据，使用特殊格式便于前端解析和渲染
                papers_data = []
                for paper in related_papers:
                    paper_info = {
                        "title": paper.title,
                        "authors": paper.authors,
                        "categories": paper.categories,
                        "url": paper.pdf_url if paper.pdf_url else ""
                    }
                    papers_data.append(paper_info)
                
                # 将论文数据转换为JSON字符串
                papers_json = json.dumps({"type": "papers_data", "papers": papers_data})
                # 返回一个特殊标记，前端可以通过检测这个标记来解析和显示相关论文
                yield f"<!-- PAPERS_DATA:{papers_json} -->", False
            
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