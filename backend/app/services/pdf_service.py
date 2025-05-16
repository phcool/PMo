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
import aiohttp
import oss2
from urllib.parse import quote

from app.services.vector_search_service import vector_search_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class PdfService:
    """Service for handling PDF file processing, text extraction, and vector embedding."""
    
    def __init__(self):
        # Configuration
        self.project_root = Path(__file__).parent.parent.parent
        self.upload_dir = self.project_root / "cached_pdfs"
        self.chunk_size = int(os.getenv("PDF_CHUNK_SIZE", "1000"))  # Characters per chunk
        self.chunk_overlap = int(os.getenv("PDF_CHUNK_OVERLAP", "200"))  # Overlap between chunks
        self.max_tokens_per_chunk = int(os.getenv("PDF_MAX_TOKENS", "4000"))  # Max tokens for each chunk
        self.file_expiry_hours = float(os.getenv("PDF_FILE_EXPIRY_HOURS", "0.5"))  # 文件过期时间（小时），默认30分钟
        
        # 阿里云 OSS 配置
        self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "")
        self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
        self.oss_endpoint = os.getenv("OSS_ENDPOINT", "")
        self.oss_bucket_name = os.getenv("OSS_BUCKET_NAME", "")
        self.oss_papers_prefix = os.getenv("OSS_PAPERS_PREFIX", "papers/")
        
        # 文件访问记录，用于跟踪文件最后访问时间 {"file_path": {"last_access": timestamp, "chat_id": "chat_id"}}
        self.file_access_records = {}
        
        # 确保上传目录存在
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # 启动后台清理任务
        asyncio.create_task(self._start_cleanup_task())
        
        logger.info(f"PDF Service initialized. Upload dir: {self.upload_dir}, Chunk size: {self.chunk_size}, Overlap: {self.chunk_overlap}, File expiry: {self.file_expiry_hours}h")
    
    async def get_pdf_from_oss(self, paper_id: str, filename: str = None) -> str:
        """
        根据论文ID从阿里云OSS获取PDF文件并保存到本地
        
        Args:
            paper_id: 论文ID，如 "2303.12345" 或 "2505_09615v1"
            filename: 可选的自定义文件名
            
        Returns:
            保存的本地文件路径
        """
        try:
            # 日志记录请求细节
            logger.info(f"Attempting to get PDF from OSS for paper_id: {paper_id}, custom filename: {filename}")
            
            # 清理paper_id，移除可能的非法字符
            sanitized_paper_id = re.sub(r'[^\w\.-]', '_', paper_id)
            if sanitized_paper_id != paper_id:
                logger.info(f"Sanitized paper_id from '{paper_id}' to '{sanitized_paper_id}'")
                paper_id = sanitized_paper_id
            
            match_format = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
            
            year = None
            month = None
            
            year, month, number = match_format.groups()
            # 使用标准格式 papers/YY/MM/YYMM_xxxxx.pdf
            paper_id=paper_id.replace('.', '_')
            oss_key = f"{self.oss_papers_prefix}{year}/{month}/{paper_id}.pdf"
            # 创建对应的本地目录结构
            local_dir = self.upload_dir / year / month
            
            # 确保本地目录存在
            os.makedirs(local_dir, exist_ok=True)
            
            # 使用与OSS相同的文件名保存到本地
            local_filename = f"{paper_id}.pdf"
            if filename:  # 如果提供了特定文件名，保存一个备份文件名
                name, ext = os.path.splitext(filename)
                if not ext.lower() == '.pdf':
                    ext = '.pdf'
                local_filename = f"{paper_id}_{name}{ext}"
            
            # 完整的本地文件路径
            local_file_path = local_dir / local_filename
            # 检查文件是否已经存在本地
            if await aiofiles.os.path.exists(local_file_path):
                logger.info(f"PDF file already exists locally at {local_file_path}")
                # 更新文件访问时间
                self._update_file_access(str(local_file_path), None)
                return str(local_file_path)
            
            logger.info(f"PDF file not found locally, trying to get from OSS with key: {oss_key}")
            
            # 记录OSS配置信息（排除敏感信息）
            logger.info(f"Using OSS endpoint: {self.oss_endpoint}, bucket: {self.oss_bucket_name}")
            
            # 初始化OSS客户端
            try:
                auth = oss2.Auth(self.oss_access_key_id, self.oss_access_key_secret)
                bucket = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
                logger.info("Successfully initialized OSS client")
            except Exception as e:
                logger.error(f"Failed to initialize OSS client: {str(e)}")
                return ""
            
            # 直接从OSS下载文件
            try:
                logger.info(f"Attempting to download object from OSS with key: {oss_key}")
                # 下载文件到临时内存
                result = bucket.get_object(oss_key)
                file_content = result.read()
                logger.info(f"Successfully downloaded {len(file_content)} bytes from OSS")
            except oss2.exceptions.NoSuchKey:
                logger.error(f"OSS key not found: {oss_key}")
                return ""
            except oss2.exceptions.OssError as e:
                logger.error(f"OSS error during download: {str(e)}")
                return ""
            except Exception as e:
                logger.error(f"Unexpected error during OSS download: {str(e)}")
                return ""
            
            # 如果没有获取到内容，返回空字符串
            if not file_content:
                logger.error(f"Failed to download PDF for paper ID: {paper_id}")
                return ""
            
            # 保存到本地文件
            try:
                async with aiofiles.open(local_file_path, 'wb') as f:
                    await f.write(file_content)
                logger.info(f"Successfully saved downloaded PDF to {local_file_path} ({len(file_content)} bytes)")
            except Exception as e:
                logger.error(f"Failed to save PDF file to {local_file_path}: {str(e)}")
                return ""
            
            # 记录文件访问时间
            self._update_file_access(str(local_file_path), None)  # 初始时chat_id未知
            
            logger.info(f"Successfully downloaded and saved PDF from OSS to {local_file_path}")
            return str(local_file_path)
            
        except Exception as e:
            logger.error(f"Error getting PDF from OSS for paper ID {paper_id}: {str(e)}", exc_info=True)
            return ""
    
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
                # 每30分钟运行一次清理
                await asyncio.sleep(1800)  # 1800秒 = 30分钟
                await self._cleanup_expired_files()
            except Exception as e:
                logger.error(f"Error in file cleanup task: {str(e)}")
    
    async def _cleanup_expired_files(self):
        """清理过期的PDF文件"""
        logger.info("Starting scheduled cleanup of PDF files")
        current_time = time.time()
        expiry_seconds = self.file_expiry_hours * 3600
        
        # 获取所有活跃的聊天会话ID和它们引用的文件
        from app.services.chat_service import chat_service
        active_chat_files = {}  # { file_path: [chat_id1, chat_id2, ...] }
        
        # 1. 收集所有活跃会话中引用的文件路径
        for chat_id, data in chat_service.active_chats.items():
            file_paths = data.get("file_paths", [])
            if not file_paths and "file_path" in data:  # 兼容旧版本单文件引用
                file_paths = [data["file_path"]]
            
            for file_path in file_paths:
                if file_path:
                    if file_path not in active_chat_files:
                        active_chat_files[file_path] = []
                    active_chat_files[file_path].append(chat_id)
        
        # 2. 整理文件访问记录，找出需要检查的文件
        files_to_check = {}  # { file_path: last_access_time }
        for file_path, record in list(self.file_access_records.items()):
            # 如果文件不在磁盘上，直接从记录中删除
            if not await aiofiles.os.path.exists(file_path):
                del self.file_access_records[file_path]
                continue
                
            last_access = record["last_access"]
            associated_chat_ids = []
            
            # 收集所有与此文件关联的聊天ID
            if "chat_id" in record and record["chat_id"]:
                associated_chat_ids.append(record["chat_id"])
            
            # 添加从active_chat_files找到的相关聊天ID
            if file_path in active_chat_files:
                associated_chat_ids.extend(active_chat_files[file_path])
            
            # 如果文件与活跃会话关联，更新最后访问时间
            if associated_chat_ids:
                # 文件被活跃会话引用，刷新最后访问时间
                record["last_access"] = current_time
                continue
            
            # 如果文件没有关联任何会话且已过期，加入检查列表
            if current_time - last_access > expiry_seconds:
                files_to_check[file_path] = last_access
        
        # 3. 检查文件是否是缓存结构中的子目录文件
        files_to_delete = []
        for file_path in files_to_check:
            # 确保文件路径是upload_dir下的文件
            rel_path = Path(file_path).relative_to(self.upload_dir) if str(file_path).startswith(str(self.upload_dir)) else None
            if rel_path:
                files_to_delete.append(file_path)
            else:
                # 不是缓存目录下的文件，保留记录但不删除
                logger.warning(f"File {file_path} is not in cache directory, skipping deletion")
        
        # 4. 删除确认无引用且过期的文件
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                if await aiofiles.os.path.exists(file_path):
                    await aiofiles.os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted expired file with no active references: {file_path}")
                    
                # 从记录中移除
                if file_path in self.file_access_records:
                    del self.file_access_records[file_path]
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        # 5. 清理空目录
        await self._cleanup_empty_directories(self.upload_dir)
        
        logger.info(f"Cleanup completed. Deleted {deleted_count} unreferenced files.")
    
    async def _cleanup_empty_directories(self, parent_dir):
        """递归清理空目录"""
        try:
            for item in os.listdir(parent_dir):
                dir_path = os.path.join(parent_dir, item)
                if os.path.isdir(dir_path):
                    await self._cleanup_empty_directories(dir_path)
                    
            # 检查目录是否为空（在清理完子目录后）
            if not os.listdir(parent_dir) and parent_dir != self.upload_dir:
                os.rmdir(parent_dir)
                logger.info(f"Removed empty directory: {parent_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up directory {parent_dir}: {str(e)}")
    
    def _is_file_in_active_chat(self, file_path: str, chat_id: Optional[str]) -> bool:
        """检查文件是否属于活跃的聊天会话"""
        from app.services.chat_service import chat_service
        
        # 如果没有关联的chat_id，文件不在活跃会话中
        if not chat_id:
            return False
        
        # 检查聊天会话是否仍然活跃
        if chat_id in chat_service.active_chats:
            active_file_path = chat_service.active_chats[chat_id].get("file_path")
            # 如果聊天会话中的文件路径与当前文件匹配，则文件仍在使用中
            return active_file_path == file_path
        
        # 额外安全检查 - 遍历所有活跃聊天，确保文件没有被其他会话使用
        for active_chat_id, data in chat_service.active_chats.items():
            if data.get("file_path") == file_path:
                return True
            
        return False
    
    # 更新其他方法，添加文件访问记录更新
    
    async def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text content from a PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        # 更新文件访问时间
        self._update_file_access(file_path)
        
        # Check if file exists
        if not await aiofiles.os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return ""
        
        try:
            # Read the PDF file
            # Note: PyPDF2 doesn't have async support, so we use a thread pool
            loop = asyncio.get_event_loop()
            text_content = await loop.run_in_executor(None, self._extract_text_sync, file_path)
            
            # Clean the text
            text_content = self._clean_text(text_content)
            
            logger.info(f"Extracted {len(text_content)} characters from PDF: {file_path}")
            return text_content
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            return ""
    
    def _extract_text_sync(self, file_path: str) -> str:
        """
        Synchronous function to extract text from PDF (runs in thread pool)
        """
        text_content = ""
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from each page
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n\n"
        
        return text_content
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text for better processing
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove headers, footers, and page numbers (simplified approach)
        text = re.sub(r'\n\d+\n', ' ', text)  # Simple page number removal
        
        # Remove Unicode control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks for processing
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Get chunk with specified size
            end = start + self.chunk_size
            
            # If we're not at the end, try to break at a sentence or paragraph
            if end < len(text):
                # Try to find a paragraph break
                paragraph_break = text.rfind('\n\n', start, end)
                if paragraph_break != -1 and paragraph_break > start + self.chunk_size / 2:
                    end = paragraph_break + 2  # Include the newlines
                else:
                    # Try to find a sentence break (period followed by space)
                    sentence_break = text.rfind('. ', start, end)
                    if sentence_break != -1 and sentence_break > start + self.chunk_size / 2:
                        end = sentence_break + 2  # Include the period and space
            
            # Add chunk to list
            chunk = text[start:end].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
            
            # Move the start position for the next chunk, accounting for overlap
            start = max(start, end - self.chunk_overlap)
        
        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
    
    async def create_vector_store(self, file_path: str, chat_id: str) -> bool:
        """
        Process a PDF file and create vector embeddings
        
        Args:
            file_path: Path to the PDF file
            chat_id: Unique identifier for the chat session
            
        Returns:
            True if successful, False otherwise
        """
        # 更新文件访问时间和关联的chat_id
        self._update_file_access(file_path, chat_id)
        
        try:
            # Extract text from PDF
            text_content = await self.extract_text_from_pdf(file_path)
            if not text_content:
                logger.error(f"Failed to extract text from PDF: {file_path}")
                return False
            
            # Split text into chunks
            chunks = self.chunk_text(text_content)
            if not chunks:
                logger.error(f"No valid chunks created from PDF: {file_path}")
                return False
            
            # 批量处理嵌入，每批最多10个
            batch_size = 10  # 根据API限制设置批处理大小
            all_embeddings = []
            
            # 分批处理所有文本块
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}, size: {len(batch_chunks)}")
                
                # 获取当前批次的嵌入
                batch_embeddings = await llm_service.get_embeddings(
                    texts=batch_chunks,
                    model=llm_service.default_embedding_model,
                )
                
                if batch_embeddings is None:
                    logger.error(f"Failed to get embeddings for batch {i//batch_size + 1}")
                    return False
                
                # 累积所有嵌入
                all_embeddings.extend(batch_embeddings)
                
                # 添加短暂延迟，避免API速率限制
                await asyncio.sleep(0.5)
            
            # 确保我们有所有块的嵌入
            if len(all_embeddings) != len(chunks):
                logger.error(f"Embedding count mismatch: got {len(all_embeddings)}, expected {len(chunks)}")
                return False
            
            # Store the chunks and embeddings in memory for this session
            self._store_session_vectors(chat_id, chunks, all_embeddings)
            
            logger.info(f"Successfully created vector store for chat session: {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating vector store for PDF {file_path}: {str(e)}")
            return False
    
    # In-memory storage for session vectors
    _session_vectors = {}  # Maps chat_id to {"chunks": List[str], "embeddings": List[List[float]]}
    
    def _store_session_vectors(self, chat_id: str, chunks: List[str], embeddings: List[List[float]]):
        """Store vectors for a specific chat session, appending to existing vectors if present"""
        # 检查该会话是否已有向量存储
        if chat_id in self._session_vectors:
            # 获取现有的数据
            existing_data = self._session_vectors[chat_id]
            existing_chunks = existing_data["chunks"]
            existing_embeddings = existing_data["embeddings"]
            
            # 追加新的数据
            self._session_vectors[chat_id] = {
                "chunks": existing_chunks + chunks,
                "embeddings": existing_embeddings + embeddings
            }
            logger.info(f"Appended {len(chunks)} new chunks to existing vector store for chat session: {chat_id}")
        else:
            # 如果不存在，创建新的向量存储
            self._session_vectors[chat_id] = {
                "chunks": chunks, 
                "embeddings": embeddings
            }
            logger.info(f"Created new vector store with {len(chunks)} chunks for chat session: {chat_id}")
    
    def get_session_vectors(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get vectors for a specific chat session"""
        return self._session_vectors.get(chat_id)
    
    async def delete_uploaded_file(self, file_path: str) -> bool:
        """
        Delete an uploaded PDF file from disk
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            if not file_path or not await aiofiles.os.path.exists(file_path):
                logger.warning(f"File not found for deletion: {file_path}")
                return False
            
            # 从文件访问记录中移除
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
        """
        Retrieve chunks most similar to the query
        
        Args:
            chat_id: Chat session ID
            query: Query text
            top_k: Number of chunks to retrieve
            
        Returns:
            List of relevant text chunks
        """
        session_data = self.get_session_vectors(chat_id)
        if not session_data:
            logger.error(f"No vector store found for chat session: {chat_id}")
            return []
        
        chunks = session_data["chunks"]
        stored_embeddings = session_data["embeddings"]
        
        # Get query embedding
        query_embedding_list = await llm_service.get_embeddings(
            texts=[query],
            model=llm_service.default_embedding_model,
        )
        
        if not query_embedding_list:
            logger.error(f"Failed to get embedding for query: {query}")
            return []
        
        query_embedding = query_embedding_list[0]
        
        # Calculate cosine similarity with each chunk
        similarities = []
        for i, emb in enumerate(stored_embeddings):
            # Convert to numpy arrays for vector operations
            emb_array = np.array(emb)
            query_array = np.array(query_embedding)
            
            # Calculate cosine similarity
            dot_product = np.dot(emb_array, query_array)
            emb_norm = np.linalg.norm(emb_array)
            query_norm = np.linalg.norm(query_array)
            similarity = dot_product / (emb_norm * query_norm)
            
            similarities.append((i, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Get top-k chunks
        top_chunks = []
        for idx, _ in similarities[:top_k]:
            top_chunks.append(chunks[idx])
        
        logger.info(f"Retrieved {len(top_chunks)} relevant chunks for query in chat session: {chat_id}")
        return top_chunks
    
    async def save_uploaded_pdf(self, file_content: bytes, filename: str) -> str:
        """
        Save uploaded PDF file to disk
        
        Args:
            file_content: PDF file content bytes
            filename: Original filename
            
        Returns:
            Path to saved file
        """
        try:
            logger.info(f"Saving uploaded PDF: {filename}")
            
            # Sanitize filename
            safe_filename = re.sub(r'[^\w\.-]', '_', filename)
            if safe_filename != filename:
                logger.info(f"Sanitized filename from '{filename}' to '{safe_filename}'")
                filename = safe_filename
            
            # Generate unique filename to avoid conflicts
            file_id = str(uuid.uuid4())
            unique_filename = f"{file_id}_{filename}"
            
            # Save to upload directory
            file_path = os.path.join(self.upload_dir, unique_filename)
            
            # Write file to disk
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
                
            logger.info(f"Successfully saved uploaded PDF to {file_path} ({len(file_content)} bytes)")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving uploaded PDF {filename}: {str(e)}")
            return ""

# Instantiate a singleton
pdf_service = PdfService() 