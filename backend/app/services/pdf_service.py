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
from urllib.parse import quote
import json

from app.services.vector_search_service import vector_search_service
from app.services.llm_service import llm_service
from app.services.oss_service import oss_service

logger = logging.getLogger(__name__)

class PdfService:
    """Service for handling PDF file processing, text extraction, and vector embedding."""
    
    def __init__(self):
        # Configuration
        self.project_root = Path(__file__).parent.parent.parent
        self.upload_dir = self.project_root / "cached_pdfs"
        self.chunk_size = int(os.getenv("PDF_CHUNK_SIZE", "1000"))  # Characters per chunk
        self.chunk_overlap = int(os.getenv("PDF_CHUNK_OVERLAP", "200"))  # Overlap between chunks
        self.max_tokens_per_chunk = int(os.getenv("PDF_MAX_TOKENS", "3000"))  # Max tokens for each chunk
        self.file_expiry_hours = float(os.getenv("PDF_FILE_EXPIRY_HOURS", "0.5"))  # 文件过期时间（小时），默认30分钟
        
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
            # 使用oss_service下载论文
            local_file_path = await oss_service.download_paper_from_oss(
                paper_id=paper_id,
                target_dir=self.upload_dir,
                custom_filename=filename
            )
            
            # 如果成功获取文件，更新文件访问记录
            if local_file_path:
                self._update_file_access(local_file_path, None)  # 初始时chat_id未知
                logger.info(f"Successfully got PDF from OSS service: {local_file_path}")
                return local_file_path
            else:
                logger.error(f"Failed to get PDF from OSS for paper ID: {paper_id}")
                return ""
                
        except Exception as e:
            logger.error(f"Error in get_pdf_from_oss for paper ID {paper_id}: {str(e)}", exc_info=True)
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
    
    async def update_chat_files(self, chat_id: str, file_path: str, paper_id: str, paper_title: Optional[str] = None) -> Dict[str, Any]:
        """
        更新聊天会话的文件列表，避免重复添加同一篇论文
        
        Args:
            chat_id: 聊天会话ID
            file_path: PDF文件路径
            paper_id: 论文ID
            paper_title: 论文标题，用于显示更友好的文件名
            
        Returns:
            包含更新状态的字典，例如 {"success": True, "already_exists": False, "file_info": {...}}
        """
        try:
            # 导入chat_service，避免循环引用
            from app.services.chat_service import chat_service
            
            # 检查聊天会话是否存在
            if chat_id not in chat_service.active_chats:
                logger.error(f"Chat session not found: {chat_id}")
                return {"success": False, "error": "Chat session not found"}
            
            # 生成友好的文件名
            filename = f"{paper_id}.pdf"
            if paper_title:
                # 清理标题中的特殊字符，使其适合作为文件名
                clean_title = re.sub(r'[^\w\s-]', '', paper_title).strip()
                # 将空格替换为下划线，避免文件名中的空格
                clean_title = re.sub(r'\s+', '_', clean_title)
                # 限制长度
                if len(clean_title) > 100:
                    clean_title = clean_title[:97] + "..."
                filename = f"{clean_title} ({paper_id}).pdf"
            
            # 检查是否是该会话的第一个PDF
            is_first_pdf = "files" not in chat_service.active_chats[chat_id]
            
            # 初始化文件列表（如果不存在）
            if is_first_pdf:
                chat_service.active_chats[chat_id]["files"] = []
            
            # 检查是否已经添加了相同的paper_id
            existing_files = chat_service.active_chats[chat_id].get("files", [])
            for existing_file in existing_files:
                if existing_file.get("paper_id") == paper_id:
                    logger.info(f"Paper {paper_id} already exists in chat session {chat_id}")
                    
                    # 更新当前活跃文件路径（即使是已存在的文件）
                    chat_service.active_chats[chat_id]["file_path"] = existing_file["file_path"]
                    
                    # 更新会话关联的论文ID
                    chat_service.active_chats[chat_id]["paper_id"] = paper_id
                    
                    return {
                        "success": True, 
                        "already_exists": True, 
                        "file_info": existing_file
                    }
            
            # 创建新的文件信息对象
            file_info = {
                "file_path": file_path,
                "filename": filename,
                "paper_id": paper_id,
                "id": str(uuid.uuid4()),  # 为文件添加唯一ID，用于API引用
                "added_at": datetime.now().isoformat()
            }
            
            # 添加当前文件到文件列表
            chat_service.active_chats[chat_id]["files"].append(file_info)
            
            # 更新当前活跃文件路径
            chat_service.active_chats[chat_id]["file_path"] = file_path
            
            # 更新会话关联的论文ID
            chat_service.active_chats[chat_id]["paper_id"] = paper_id
            
            logger.info(f"Added paper {paper_id} to chat session {chat_id}")
            return {
                "success": True, 
                "already_exists": False, 
                "file_info": file_info
            }
            
        except Exception as e:
            logger.error(f"Error updating chat files for session {chat_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def query_similar_chunks(self, chat_id: str, query: str, top_k: int = 3) -> List[str]:
        """
        Retrieve chunks most similar to the query, supporting multiple uploaded files.
        """
        from app.services.chat_service import chat_service
        session = chat_service.active_chats.get(chat_id)
        if not session:
            logger.error(f"No session found for chat_id: {chat_id}")
            return []
        files = session.get("files", [])
        if not files:
            logger.error(f"No files found in session for chat_id: {chat_id}")
            return []
        import re
        from pathlib import Path
        import json
        all_chunks = []
        all_embeddings = []
        for file_info in files:
            paper_id = file_info.get("paper_id")
            if not paper_id:
                continue
            match = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
            if not match:
                logger.warning(f"Invalid paper_id format: {paper_id}")
                continue
            year, month, _ = match.groups()
            local_path = Path("cached_embeddings") / year / month / f"{paper_id.replace('.', '_')}.json"
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
        # 计算 query embedding
        query_embedding_list = await llm_service.get_embeddings(
            texts=[query],
            model=llm_service.default_embedding_model,
        )
        if not query_embedding_list:
            logger.error(f"Failed to get embedding for query: {query}")
            return []
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
        top_chunks = [all_chunks[idx] for idx, _ in similarities[:top_k]]
        logger.info(f"Retrieved {len(top_chunks)} relevant chunks for query in chat session: {chat_id} (from {len(files)} files)")
        return top_chunks

    async def generate_embeddings_for_paper(self, paper_id: str, file_path: str) -> Tuple[List[str], List[List[float]], str]:
        """
        为论文PDF生成embeddings，并保存到本地和OSS
        
        Args:
            paper_id: 论文ID
            file_path: PDF文件路径
            
        Returns:
            Tuple[List[str], List[List[float]], str]: (chunks, embeddings, local_path)
            如果生成失败，返回 ([], [], "")
        """
        try:
            # 1. 解析年份和月份
            match = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
            if not match:
                logger.error(f"Invalid paper_id format: {paper_id}")
                return [], [], ""
                
            year, month, _ = match.groups()
            local_dir = Path("cached_embeddings") / year / month
            local_dir.mkdir(parents=True, exist_ok=True)
            local_path = local_dir / f"{paper_id.replace('.', '_')}.json"
            
            # 2. 从PDF提取文本并分块
            text_content = await self.extract_text_from_pdf(file_path)
            if not text_content:
                logger.error(f"Failed to extract text from PDF for paper_id: {paper_id}")
                return [], [], ""
            
            chunks = self.chunk_text(text_content)
            if not chunks:
                logger.error(f"No valid chunks generated from PDF for paper_id: {paper_id}")
                return [], [], ""
            
            # 3. 分批生成embeddings
            BATCH_SIZE = 10
            all_embeddings = []
            
            for i in range(0, len(chunks), BATCH_SIZE):
                batch_chunks = chunks[i:i + BATCH_SIZE]
                logger.info(f"Processing embedding batch {i//BATCH_SIZE + 1}/{(len(chunks)-1)//BATCH_SIZE + 1} for paper {paper_id}")
                
                batch_embeddings = await llm_service.get_embeddings(
                    texts=batch_chunks,
                    model=llm_service.default_embedding_model
                )
                
                if not batch_embeddings or len(batch_embeddings) != len(batch_chunks):
                    logger.error(f"Failed to generate embeddings for batch {i//BATCH_SIZE + 1} of paper_id: {paper_id}")
                    return [], [], ""
                
                all_embeddings.extend(batch_embeddings)
                
                # 添加小延迟，避免请求过于频繁
                if i + BATCH_SIZE < len(chunks):
                    await asyncio.sleep(0.5)
            
            if len(all_embeddings) != len(chunks):
                logger.error(f"Generated embeddings count ({len(all_embeddings)}) doesn't match chunks count ({len(chunks)})")
                return [], [], ""
            
            # 4. 保存到本地
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump({"chunks": chunks, "embeddings": all_embeddings}, f)
            logger.info(f"Generated and cached embeddings to {local_path}")
            
            # 5. 上传到OSS
            try:
                await oss_service.upload_vector_embeddings(paper_id, chunks, all_embeddings)
                logger.info(f"Uploaded embeddings to OSS for paper_id: {paper_id}")
            except Exception as e:
                logger.error(f"Failed to upload embeddings to OSS for paper_id {paper_id}: {str(e)}")
                # 继续执行，因为本地缓存已经成功
            
            return chunks, all_embeddings, str(local_path)
            
        except Exception as e:
            logger.error(f"Error generating embeddings for paper {paper_id}: {str(e)}", exc_info=True)
            return [], [], ""

# Instantiate a singleton
pdf_service = PdfService() 