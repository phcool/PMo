import os
import logging
import tempfile
import PyPDF2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import aiofiles
import aiofiles.os
import asyncio
from pathlib import Path
import re
import time
import uuid
import glob
from datetime import datetime, timedelta
import oss2 # For Alibaba Cloud OSS

from app.services.vector_search_service import vector_search_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class PdfService:
    """Service for handling PDF file processing, text extraction, and vector embedding."""
    
    def __init__(self):
        # Configuration
        self.project_root = Path(__file__).parent.parent.parent
        self.upload_dir = self.project_root / "uploads" / "pdfs"
        self.chunk_size = int(os.getenv("PDF_CHUNK_SIZE", "1000"))  # Characters per chunk
        self.chunk_overlap = int(os.getenv("PDF_CHUNK_OVERLAP", "200"))  # Overlap between chunks
        self.max_tokens_per_chunk = int(os.getenv("PDF_MAX_TOKENS", "4000"))  # Max tokens for each chunk
        self.file_expiry_hours = float(os.getenv("PDF_FILE_EXPIRY_HOURS", "0.5"))  # 文件过期时间（小时），默认30分钟
        
        # 文件访问记录，用于跟踪文件最后访问时间 {"file_path": {"last_access": timestamp, "chat_id": "chat_id"}}
        self.file_access_records = {}
        
        # OSS Configuration
        self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID")
        self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET")
        self.oss_endpoint = os.getenv("OSS_ENDPOINT")
        self.oss_bucket_name = os.getenv("OSS_BUCKET_NAME")
        self.oss_bucket_client = None

        if self.oss_access_key_id and self.oss_access_key_secret and self.oss_endpoint and self.oss_bucket_name:
            try:
                auth = oss2.Auth(self.oss_access_key_id, self.oss_access_key_secret)
                self.oss_bucket_client = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
                logger.info(f"OSS client initialized for bucket: {self.oss_bucket_name} at endpoint: {self.oss_endpoint}")
            except Exception as e:
                logger.error(f"Failed to initialize OSS client: {e}", exc_info=True)
                self.oss_bucket_client = None # Ensure it's None if initialization fails
        else:
            logger.warning("OSS configuration variables are not fully set in PdfService. PDF download from OSS will be disabled.")

        # 确保上传目录存在
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # 启动后台清理任务
        asyncio.create_task(self._start_cleanup_task())
        
        logger.info(f"PDF Service initialized. Upload dir: {self.upload_dir}, Chunk size: {self.chunk_size}, Overlap: {self.chunk_overlap}, File expiry: {self.file_expiry_hours}h")
    
    async def _save_pdf_content_to_local_file(self, file_content: bytes, original_filename_hint: str) -> str:
        """
        Internal helper to save PDF content to a unique local file.
        Uses similar naming convention to save_uploaded_pdf.
        """
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        original_name, ext = os.path.splitext(original_filename_hint)
        if not ext.lower() == '.pdf':
            ext = '.pdf'
        
        safe_name = re.sub(r'[^\w\-_\.]', '_', original_name)
        safe_name = safe_name[:50]
        
        final_filename = f"{timestamp}_{unique_id}_oss_{safe_name}{ext}" # Add 'oss' marker
        file_path = self.upload_dir / final_filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        self._update_file_access(str(file_path), None)
        logger.info(f"Saved PDF content (from OSS or other source) to {file_path}")
        return str(file_path)

    async def download_and_save_pdf_from_oss(self, paper_id: str) -> Optional[str]:
        """
        Downloads a PDF from OSS based on paper_id, saves it locally, and returns the local path.
        """
        if not self.oss_bucket_client:
            logger.error(f"OSS client not available. Cannot download PDF for paper {paper_id} from OSS.")
            return None

        original_paper_id = paper_id
        
        temp_id_for_filename = original_paper_id
        if 'v' in original_paper_id.split('.')[-1] and original_paper_id.count('.') > 0:
            last_dot_index = original_paper_id.rfind('.')
            temp_id_for_filename = original_paper_id[:last_dot_index] + '_' + original_paper_id[last_dot_index+1:]
        
        sanitized_file_name_base = re.sub(r'[/:.]', '_', temp_id_for_filename.replace('.pdf',''))
        sanitized_file_name_for_oss_object = f"{sanitized_file_name_base}.pdf" # Filename part of the OSS key

        year_prefix = ""
        month_prefix = ""
        match_new = re.match(r'^(\d{2})(\d{2})\.\d+', original_paper_id)
        match_old_style_category = re.match(r'^[a-zA-Z\-]+(?:\.[a-zA-Z]{2})?/(\d{2})(\d{2})\d+', original_paper_id)
        match_old_no_category = re.match(r'^(\d{2})(\d{2})\d{3,}', original_paper_id)

        if match_new:
            year_prefix = match_new.group(1)
            month_prefix = match_new.group(2)
        elif match_old_style_category:
            year_prefix = match_old_style_category.group(1)
            month_prefix = match_old_style_category.group(2)
        elif match_old_no_category:
            year_prefix = match_old_no_category.group(1)
            month_prefix = match_old_no_category.group(2)

        if year_prefix and month_prefix:
            object_key = f"papers/{year_prefix}/{month_prefix}/{sanitized_file_name_for_oss_object}"
        else:
            logger.warning(f"Could not parse year/month from paper ID '{original_paper_id}' for OSS. Using fallback path.")
            object_key = f"papers/unknown_date_format/{sanitized_file_name_for_oss_object}"
        
        logger.info(f"Attempting to download PDF for paper {original_paper_id} from OSS. Object key: {object_key}")
        try:
            # OSS SDK operations are typically synchronous, run in executor if truly async needed
            # For simplicity here, assuming oss2.Bucket methods can be called if this whole service runs in async context
            # If oss2 is strictly sync, this part needs to be wrapped with loop.run_in_executor
            loop = asyncio.get_event_loop()
            pdf_object = await loop.run_in_executor(None, self.oss_bucket_client.get_object, object_key)
            pdf_content = pdf_object.read()
            
            if not pdf_content:
                logger.error(f"Downloaded empty PDF content for {original_paper_id} from OSS key {object_key}")
                return None
            logger.info(f"Successfully downloaded PDF for {original_paper_id} from OSS ({len(pdf_content)} bytes).")

            # Save the downloaded content to a local file
            local_file_path = await self._save_pdf_content_to_local_file(pdf_content, f"{sanitized_file_name_base}.pdf")
            return local_file_path

        except oss2.exceptions.NoSuchKey:
            logger.warning(f"PDF not found in OSS for paper {original_paper_id} with key {object_key}.")
            return None
        except oss2.exceptions.OssError as e:
            logger.error(f"OSS error downloading PDF for {original_paper_id} (key: {object_key}): {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading/saving PDF from OSS for {original_paper_id}: {e}", exc_info=True)
            return None

    async def save_uploaded_pdf(self, file_content: bytes, filename: str) -> str:
        """
        Save an uploaded PDF file to disk with improved naming (original method for direct uploads)
        """
        local_file_path = await self._save_pdf_content_to_local_file(file_content, filename)
        # The _save_pdf_content_to_local_file already logs and updates access time.
        # We can differentiate log message slightly if needed, but core logic is shared.
        logger.info(f"Saved user-uploaded PDF ({filename}) to {local_file_path}")
        return local_file_path
    
    def _update_file_access(self, file_path: str, chat_id: Optional[str] = None):
        """更新文件访问记录"""
        current_time = time.time()
        if file_path in self.file_access_records:
            record = self.file_access_records[file_path]
            record["last_access"] = current_time
            if chat_id and not record.get("chat_id"):  # 只在首次设置chat_id
                record["chat_id"] = chat_id
        else:
            self.file_access_records[file_path] = {
                "last_access": current_time,
                "chat_id": chat_id
            }
    
    async def _start_cleanup_task(self):
        """启动定期清理过期文件的任务"""
        while True:
            try:
                await asyncio.sleep(1800) 
                await self._cleanup_expired_files()
            except Exception as e:
                logger.error(f"Error in file cleanup task: {str(e)}")
    
    async def _cleanup_expired_files(self):
        """清理过期的PDF文件"""
        logger.info("Starting scheduled cleanup of PDF files")
        current_time = time.time()
        expiry_seconds = self.file_expiry_hours * 3600
        
        expired_files = []
        for file_path, record in list(self.file_access_records.items()):
            last_access = record["last_access"]
            chat_id = record.get("chat_id")
            
            if not self._is_file_in_active_chat(file_path, chat_id):
                if current_time - last_access > expiry_seconds:
                    expired_files.append(file_path)
                    del self.file_access_records[file_path]
        
        from app.services.chat_service import chat_service
        active_file_paths = set()
        
        for chat_id, data in chat_service.active_chats.items():
            file_path = data.get("file_path")
            if file_path:
                active_file_paths.add(file_path)
        
        for file_path in list(self.file_access_records.keys()):
            if file_path not in active_file_paths:
                record = self.file_access_records[file_path]
                file_age = current_time - record.get("last_access", current_time)
                if file_age > expiry_seconds:
                    if file_path not in expired_files:
                        expired_files.append(file_path)
                        del self.file_access_records[file_path]
        
        deleted_count = 0
        for file_path in expired_files:
            try:
                if await aiofiles.os.path.exists(file_path):
                    await aiofiles.os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        try:
            all_files = set(glob.glob(str(self.upload_dir / "*.pdf")))
            tracked_files = set(self.file_access_records.keys())
            orphan_files = all_files - tracked_files
            
            for file_path in orphan_files:
                try:
                    file_stat = await aiofiles.os.stat(file_path)
                    create_time = file_stat.st_ctime
                    if current_time - create_time > 300: 
                        await aiofiles.os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"Deleted orphan file: {file_path}")
                except Exception as e:
                    logger.error(f"Error processing orphan file {file_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error finding orphan files: {str(e)}")
        
        logger.info(f"Cleanup completed. Deleted {deleted_count} files.")
    
    def _is_file_in_active_chat(self, file_path: str, chat_id: Optional[str]) -> bool:
        """检查文件是否属于活跃的聊天会话"""
        from app.services.chat_service import chat_service
        if not chat_id:
            return False
        if chat_id in chat_service.active_chats:
            active_file_path = chat_service.active_chats[chat_id].get("file_path")
            return active_file_path == file_path
        for active_chat_id, data in chat_service.active_chats.items():
            if data.get("file_path") == file_path:
                return True
        return False
    
    async def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text content from a PDF file"""
        self._update_file_access(file_path)
        if not await aiofiles.os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return ""
        try:
            loop = asyncio.get_event_loop()
            text_content = await loop.run_in_executor(None, self._extract_text_sync, file_path)
            text_content = self._clean_text(text_content)
            logger.info(f"Extracted {len(text_content)} characters from PDF: {file_path}")
            return text_content
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            return ""
    
    def _extract_text_sync(self, file_path: str) -> str:
        """Synchronous function to extract text from PDF (runs in thread pool)"""
        text_content = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n\n"
        return text_content
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text for better processing"""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\d+\n', ' ', text)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        return text.strip()
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks for processing"""
        if not text: return []
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
            if chunk: chunks.append(chunk)
            start = max(start, end - self.chunk_overlap)
        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
    
    async def create_vector_store(self, file_path: str, chat_id: str) -> bool:
        """Process a PDF file and create vector embeddings"""
        self._update_file_access(file_path, chat_id)
        try:
            text_content = await self.extract_text_from_pdf(file_path)
            if not text_content:
                logger.error(f"Failed to extract text from PDF: {file_path}")
                return False
            chunks = self.chunk_text(text_content)
            if not chunks:
                logger.error(f"No valid chunks created from PDF: {file_path}")
                return False
            batch_size = 10
            all_embeddings = []
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}, size: {len(batch_chunks)}")
                batch_embeddings = await llm_service.get_embeddings(
                    texts=batch_chunks, model=llm_service.default_embedding_model,
                )
                if batch_embeddings is None:
                    logger.error(f"Failed to get embeddings for batch {i//batch_size + 1}")
                    return False
                all_embeddings.extend(batch_embeddings)
                await asyncio.sleep(0.5)
            if len(all_embeddings) != len(chunks):
                logger.error(f"Embedding count mismatch: got {len(all_embeddings)}, expected {len(chunks)}")
                return False
            self._store_session_vectors(chat_id, chunks, all_embeddings)
            logger.info(f"Successfully created vector store for chat session: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating vector store for PDF {file_path}: {str(e)}")
            return False
    
    _session_vectors = {}
    
    def _store_session_vectors(self, chat_id: str, chunks: List[str], embeddings: List[List[float]]):
        """Store vectors for a specific chat session, appending to existing vectors if present"""
        if chat_id in self._session_vectors:
            existing_data = self._session_vectors[chat_id]
            existing_chunks = existing_data["chunks"]
            existing_embeddings = existing_data["embeddings"]
            self._session_vectors[chat_id] = {
                "chunks": existing_chunks + chunks,
                "embeddings": existing_embeddings + embeddings
            }
            logger.info(f"Appended {len(chunks)} new chunks to existing vector store for chat session: {chat_id}")
        else:
            self._session_vectors[chat_id] = { "chunks": chunks, "embeddings": embeddings }
            logger.info(f"Created new vector store with {len(chunks)} chunks for chat session: {chat_id}")
    
    def get_session_vectors(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get vectors for a specific chat session"""
        return self._session_vectors.get(chat_id)
    
    async def delete_uploaded_file(self, file_path: str) -> bool:
        """Delete an uploaded PDF file from disk"""
        try:
            if not file_path or not await aiofiles.os.path.exists(file_path):
                logger.warning(f"File not found for deletion: {file_path}")
                return False
            if file_path in self.file_access_records:
                del self.file_access_records[file_path]
            await aiofiles.os.remove(file_path)
            logger.info(f"Successfully deleted uploaded PDF: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting PDF file {file_path}: {str(e)}")
            return False
    
    def cleanup_session(self, chat_id: str):
        """Clean up session data when chat is done"""
        if chat_id in self._session_vectors:
            del self._session_vectors[chat_id]
            logger.info(f"Cleaned up vector store for chat session: {chat_id}")
    
    async def query_similar_chunks(self, chat_id: str, query: str, top_k: int = 3) -> List[str]:
        """Retrieve chunks most similar to the query"""
        session_data = self.get_session_vectors(chat_id)
        if not session_data:
            logger.error(f"No vector store found for chat session: {chat_id}")
            return []
        chunks = session_data["chunks"]
        stored_embeddings = session_data["embeddings"]
        query_embedding_list = await llm_service.get_embeddings(
            texts=[query], model=llm_service.default_embedding_model,
        )
        if not query_embedding_list:
            logger.error(f"Failed to get embedding for query: {query}")
            return []
        query_embedding = query_embedding_list[0]
        similarities = []
        for i, emb in enumerate(stored_embeddings):
            emb_array = np.array(emb)
            query_array = np.array(query_embedding)
            dot_product = np.dot(emb_array, query_array)
            emb_norm = np.linalg.norm(emb_array)
            query_norm = np.linalg.norm(query_array)
            similarity = dot_product / (emb_norm * query_norm)
            similarities.append((i, similarity))
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_chunks = [chunks[idx] for idx, _ in similarities[:top_k]]
        logger.info(f"Retrieved {len(top_chunks)} relevant chunks for query in chat session: {chat_id}")
        return top_chunks

pdf_service = PdfService() 