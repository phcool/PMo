import os
import logging
import time
from typing import List, Dict, Any, AsyncGenerator, Tuple
import asyncio

from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
from app.services.db_service import db_service

logger = logging.getLogger(__name__)

class ChatService:
    """
    Service for handling chat conversations
    """
    
    def __init__(self):
        """
        initialize chat service
        """
        # chat config
        self.max_context_messages = 10
        
        # active chats
        self.active_chats = {}
        
        #  track processing files
        self.processing_files = set()
        
        logger.info(f"Chat Service initialized. Max context: {self.max_context_messages}")
    
    def add_message(self, user_id: str, role: str, content: str):
        """
        add message to a chat
        """

        if user_id not in self.active_chats:
            logger.error(f"Chat session not found: {user_id}")
            return
        
        self.active_chats[user_id]["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
    
    def get_messages(self, user_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """get user's history messages"""
        if user_id not in self.active_chats:
            self.active_chats[user_id] = {
                "messages": [],
                "files": []
            }
        messages = self.active_chats[user_id]["messages"]
        
        if limit:
            return messages[-limit:]
        return messages
    
    async def attach_paper(self, user_id: str, paper_id: str) -> bool:
        """get paper pdf and related to chat"""
        if user_id not in self.active_chats:
            self.active_chats[user_id] = {
                "messages": [],
                "files": []
            }
        try:
            paper_title = paper_id
            paper = await db_service.get_paper_by_id(paper_id)
            if paper:
                paper_title = paper.title

            file_path = await pdf_service.get_pdf(paper_id)

            success = await pdf_service.update_chat_files(user_id, file_path, paper_id, paper_title)

            if not success:
                return False

            self.add_message(
                user_id,
                "system",
                f"Paper {paper_title} is loaded and been processing"
            )
            
            logger.info(f"Added paper {paper_id} to chat session {user_id}.")
            return True
                
        except Exception as e:
            logger.error(f"Error getting PDF for paper {paper_id} for chat session {user_id}: {str(e)}", exc_info=True)
            return False

    async def process_embeddings(self, paper_id: str) -> bool:
        """
        generate embeddings for a paper and save to local directory
        """
        try:
            # if the paper is already being processed, wait for it to finish
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
    
    async def format_messages(self, user_id: str) -> List[Dict[str, str]]:
        """
        format messages for API call
        """
        chat_data = self.active_chats.get(user_id)
        
        chat_file_names = []
        if chat_data["files"]:
            for file_data in chat_data["files"]:
                chat_file_names.append(file_data.get("filename", "Unknown file"))
        
        system_content = (
            "You are a professional academic paper analysis assistant. You can analyze papers and answer questions based on the papers chunks "+
            "However, if there is no paper chunk, you can still answer the user's question based on the user's query. "
            f"There are {len(chat_file_names)} papers in user's file list: {', '.join(chat_file_names)}. Please cite specific content from the papers to help the user understand them deeply."
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
    
    async def generate_response(self, user_id: str, query: str) -> AsyncGenerator[Tuple[str, bool], None]:
        self.add_message(user_id, "user", query)
        
        chat_data = self.active_chats[user_id]
        
        try:
            relevant_chunks = []
            if chat_data["files"]:
                # get relevant chunks from pdf
                relevant_chunks = await pdf_service.query_similar_chunks(
                    user_id, 
                    query
                )
            
            # format messages
            api_messages = await self.format_messages(user_id)
            
            # add relevant chunks to the latest user message
            if relevant_chunks:
                context_text = "\n\n".join(relevant_chunks)
                last_message_idx = len(api_messages) - 1
                
                # create a new message with context
                enhanced_query = f"""
                {query}
                
                Here are some relevant content from the papers:
                ---
                {context_text}
                ---
                """
                
                api_messages[last_message_idx]["content"] = enhanced_query
        except Exception as e:
            logger.error(f"Error performing RAG for chat {user_id}: {str(e)}")
            # if failed, fallback to regular message format
            api_messages = await self.format_messages(user_id)
        
        # generate response from LLM
        assistant_response = ""
        try:
            # stream response from LLM
            stream_response = await llm_service.get_conversation_completion(
                messages=api_messages,
                temperature=llm_service.conversation_temperature
            )
            
            if not stream_response:
                error_msg = "Sorry, I encountered an error while processing your request."
                self.add_message(user_id, "assistant", error_msg)
                yield error_msg, True
                return
            
            # process each chunk of the stream response
            async for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    assistant_response += content
                    # immediately send each token
                    yield content, False
            
            # add to chat history after completion
            if assistant_response:
                self.add_message(user_id, "assistant", assistant_response)
                
            # send end flag
            yield "", True
                
        except Exception as e:
            logger.error(f"Error generating response for chat {user_id}: {str(e)}")
            error_msg = "Sorry, I encountered an error while processing your request."
            self.add_message(user_id, "assistant", error_msg)
            yield error_msg, True

chat_service = ChatService() 