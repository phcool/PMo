import os
import logging

import PyPDF2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import aiofiles
import aiofiles.os
import asyncio
from pathlib import Path
import re



from datetime import datetime
import aiohttp
import json

from pathlib import Path

from app.services.llm_service import llm_service
from app.models.paper import Paper

logger = logging.getLogger(__name__)

class PdfService:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.pdf_dir = self.project_root / "data" / "cached_pdfs"
        self.embedding_dir = self.project_root / "data" / "cached_embeddings"
        self.chunk_size = int(os.getenv("PDF_CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("PDF_CHUNK_OVERLAP", "200"))
        self.top_k = int(os.getenv("PDF_TOP_K", "20"))
        self.downloading_processes=set()
        
        os.makedirs(self.pdf_dir, exist_ok=True)
        os.makedirs(self.embedding_dir, exist_ok=True)
    
    async def get_pdf(self,paper_id:str):
        
        
        try:
            year_month = paper_id[:4]
            year = year_month[:2]
            month = year_month[2:4]
            target_dir = self.pdf_dir / year / month
            filename = f"{paper_id}.pdf"
            local_path = target_dir / filename
            if await aiofiles.os.path.exists(local_path):
                return local_path

            if paper_id in self.downloading_processes:
                while paper_id in self.downloading_processes:
                    await asyncio.sleep(0.2)
                
                if await aiofiles.os.path.exists(local_path):
                    return local_path
                else:
                    logger.error(f"PDF file not found at: {local_path}")
                    return None
                
            self.downloading_processes.add(paper_id)

            await aiofiles.os.makedirs(target_dir, exist_ok=True)

            pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
 
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url) as response:
                    if response.status == 200:
                        async with aiofiles.open(local_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        return str(local_path)
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF for paper {paper_id}: {str(e)}", exc_info=True)
            return None
        finally:
            self.downloading_processes.discard(paper_id)
    
    async def extract_text_from_pdf(self, file_path: str) -> str:
        try:
            loop = asyncio.get_event_loop()
            text_content = await loop.run_in_executor(None, self.extract_text_sync, file_path)
            
            text_content = self.clean_text(text_content)
            
            return text_content
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            return ""
    
    def extract_text_sync(self, file_path: str) -> str:
        text_content = ""
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n\n"
        
        return text_content
    
    def clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\d+\n', ' ', text)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    def chunk_text(self, text: str) -> List[str]:
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            if end < len(text):
                paragraph_break = text.rfind('\n\n', start, end)
                if paragraph_break != -1 and paragraph_break > start + self.chunk_size / 2:
                    end = paragraph_break + 2
                else:
                    sentence_break = text.rfind('. ', start, end)
                    if sentence_break != -1 and sentence_break > start + self.chunk_size / 2:
                        end = sentence_break + 2
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = max(start, end - self.chunk_overlap)
        
        return chunks
    
    
    async def update_chat_files(self, chat_id: str, file_path: str, paper_id: str, paper_title: Optional[str] = None) -> Dict[str, Any]:
        from app.services.chat_service import chat_service
        try:
            
            filename = f"{paper_id}.pdf"
            if paper_title:
                if len(paper_title) > 100:
                    paper_title = paper_title[:97] + "..."
                filename = f"{paper_title}"
            
            existing_files = chat_service.active_chats[chat_id].get("files", [])
            for existing_file in existing_files:
                if existing_file.get("paper_id") == paper_id:
                    return True
            
            file_info = {
                "file_path": file_path,
                "filename": filename,
                "paper_id": paper_id,
                "paper_URL":f"https://arxiv.org/pdf/{paper_id}.pdf",
                "added_at": datetime.now().isoformat()
            }
            
            chat_service.active_chats[chat_id]["files"].append(file_info)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating chat files for session {chat_id}: {str(e)}")
            return False

    async def query_similar_chunks(self, chat_id: str, query: str) -> List[str]:
        from app.services.chat_service import chat_service
        session = chat_service.active_chats.get(chat_id)
        files = session.get("files", [])

        all_chunks = []
        all_embeddings = []
        for file_info in files:
            paper_id = file_info.get("paper_id")

            year_month = paper_id[:4]
            year = year_month[:2]
            month = year_month[2:4]

            local_path = self.embedding_dir / year / month / f"{paper_id}.json"

            if not local_path.exists():
                logger.warning(f"Embedding file not found: {local_path}")
                continue
            
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            chunks = data.get("chunks", [])
            embeddings = data.get("embeddings", [])

            if not chunks or not embeddings or len(chunks) != len(embeddings):
                logger.warning(f"Invalid embedding data in {local_path}")
                continue

            all_chunks.extend(chunks)
            all_embeddings.extend(embeddings)

        if not all_chunks or not all_embeddings:
            logger.error(f"No valid embeddings found for any file in session {chat_id}")
            return []
        
        query_embedding_list = await llm_service.get_embeddings(
            texts=[query],
        )
        
        query_embedding = query_embedding_list[0]
        similarities = []
        for i, emb in enumerate(all_embeddings):
            emb_array = np.array(emb)
            query_array = np.array(query_embedding)
            dot_product = np.dot(emb_array, query_array)
            emb_norm = np.linalg.norm(emb_array)
            query_norm = np.linalg.norm(query_array)
            similarity = dot_product / (emb_norm * query_norm)
            similarities.append((i, similarity))
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_chunks = [all_chunks[idx] for idx, _ in similarities[:self.top_k]]
        logger.info(f"Retrieved {len(top_chunks)} relevant chunks for query in chat session: {chat_id} (from {len(files)} files)")
        return top_chunks

    async def generate_embeddings_for_paper(self, paper_id: str) -> bool:
        try:
                
            year_month = paper_id[:4]
            year = year_month[:2]
            month = year_month[2:4]
            
            pdf_path = self.pdf_dir / year / month / f"{paper_id}.pdf"
            target_dir = self.embedding_dir / year / month
            local_path = target_dir / f"{paper_id}.json"

            if local_path.exists():
                return True

            await aiofiles.os.makedirs(target_dir, exist_ok=True)
            
            text_content = await self.extract_text_from_pdf(pdf_path)
            if not text_content:
                return False
            
            chunks = self.chunk_text(text_content)
            if not chunks:
                return False

            all_embeddings = await llm_service.get_embeddings(
                texts=chunks
            )
            
            if len(all_embeddings) != len(chunks):
                logger.error(f"Generated embeddings count ({len(all_embeddings)}) doesn't match chunks count ({len(chunks)})")
                return False
            

            
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump({"chunks": chunks, "embeddings": all_embeddings}, f)
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating embeddings for paper {paper_id}: {str(e)}", exc_info=True)
            return False

pdf_service = PdfService() 