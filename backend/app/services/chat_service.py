import os
import logging
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
import asyncio

from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
from app.services.db_service import db_service

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat conversations, including RAG with PDFs."""
    
    def __init__(self):
        """Initialize chat service"""
        # chat config
        self.max_context_messages = int(os.getenv("CHAT_MAX_CONTEXT", "10"))
        
        # active chats
        self.active_chats = {}
        
        #  track processing files
        self.processing_files = set()
        
        logger.info(f"Chat Service initialized. Max context: {self.max_context_messages}")
    
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
        if chat_id not in self.active_chats:
            self.active_chats[chat_id] = {
                "messages": [],
                "files": []
            }
        messages = self.active_chats[chat_id]["messages"]
        
        if limit:
            return messages[-limit:]
        return messages
    
    def is_processing_file(self, chat_id: str) -> bool:
        for file in self.active_chats[chat_id]["files"]:
            if file["paper_id"] in self.processing_files:
                return True
        return False
    
    async def attach_paper(self, chat_id: str, paper_id: str) -> bool:
        """get paper pdf and related to chat"""
        if chat_id not in self.active_chats:
            self.active_chats[chat_id] = {
                "messages": [],
                "files": []
            }
        try:
            paper_title = paper_id
            paper = await db_service.get_paper_by_id(paper_id)
            if paper:
                paper_title = paper.title

            file_path = await pdf_service.get_pdf(paper_id)

            success = await pdf_service.update_chat_files(chat_id, file_path, paper_id, paper_title)

            if not success:
                return False

            self.add_message(
                chat_id,
                "system",
                f"Paper {paper_title} is loaded and been processing"
            )
            
            logger.info(f"Added paper {paper_id} to chat session {chat_id}.")
            return True
                
        except Exception as e:
            logger.error(f"Error getting PDF for paper {paper_id} for chat session {chat_id}: {str(e)}", exc_info=True)
            return False

    async def process_paper_embeddings(self, paper_id: str) -> bool:
        try:
            if paper_id in self.processing_files:
                while paper_id in self.processing_files:
                    await asyncio.sleep(0.2)
                return True
            
            self.processing_files.add(paper_id)

            await pdf_service.generate_embeddings_for_paper(paper_id)

            self.processing_files.discard(paper_id)
            logger.info(f"Successfully processed embeddings for paper {paper_id}")
            
            return True
        except Exception as e:
            self.processing_files.discard(paper_id)
            logger.error(f"Error processing embeddings for paper {paper_id}: {str(e)}", exc_info=True)
            return False
    
    async def _format_messages_for_api(self, chat_id: str) -> List[Dict[str, str]]:
        """Format messages for API call, including system prompt (in English, always answer user even if no PDF)"""
        chat_data = self.active_chats.get(chat_id)
        
        has_uploaded_pdfs = False
        uploaded_filenames = []
        if chat_data["files"]:
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
        self.add_message(chat_id, "user", query)
        
        chat_data = self.active_chats[chat_id]
        has_uploaded_pdfs =  chat_data["files"]
        
        if has_uploaded_pdfs:
            try:
                # 从PDF中获取相关的文本块
                relevant_chunks = await pdf_service.query_similar_chunks(
                    chat_id, 
                    query
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

chat_service = ChatService() 