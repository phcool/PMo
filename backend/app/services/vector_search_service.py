import os
import logging
import numpy as np
import faiss
import asyncio # Import asyncio
from typing import List, Tuple, Dict, Any, Optional
import pickle
from pathlib import Path
import time

from app.models.paper import Paper
from app.services.llm_service import llm_service # Import llm_service

logger = logging.getLogger(__name__)

class VectorSearchService:
    """使用FAISS和外部嵌入API进行向量搜索的服务"""
    
    def __init__(self):
        """
        初始化向量搜索服务
        """
        # 获取嵌入维度和服务相关配置 (从 llm_service 获取默认值)
        self.embedding_dim = llm_service.default_embedding_dimensions
        self.embedding_model = llm_service.default_embedding_model
        # 从环境变量读取嵌入API的批量大小，默认为10 (适配 v3 模型)
        self.embedding_batch_size = int(os.getenv("API_EMBEDDING_BATCH_SIZE", "10")) 
        
        if not self.embedding_dim:
             raise ValueError("Embedding dimension not configured in LLMService!")
             
        self.index = None
        self.paper_ids = []
        
        # Project root and data dir setup (remains the same)
        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.index_path = str(self.data_dir / "paper_index.faiss")
        self.paper_ids_path = str(self.data_dir / "paper_ids.pkl")
        
        logger.info(f"VectorSearchService initializing with {self.embedding_dim}-dim embeddings (Model: {self.embedding_model}, Batch Size: {self.embedding_batch_size})")
        logger.info(f"Index file path: {self.index_path}")
        
        # Load existing index or create a new one (remains mostly the same)
        self._load_index()
    
    def _load_index(self):
        """如果存在，则从磁盘加载FAISS索引和ID列表"""
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.paper_ids_path):
                self.index = faiss.read_index(self.index_path)
                # Check if loaded index dimension matches config
                if self.index.d != self.embedding_dim:
                     logger.warning(f"Loaded index dimension ({self.index.d}) does not match configured dimension ({self.embedding_dim}). Creating new index.")
                     self._create_new_index()
                else:
                    with open(self.paper_ids_path, 'rb') as f:
                        self.paper_ids = pickle.load(f)
                    logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors and {len(self.paper_ids)} IDs.")
                    if self.index.ntotal != len(self.paper_ids):
                         logger.warning("Index vector count and ID count mismatch! Rebuilding might be needed.")
            else:
                self._create_new_index()
        except Exception as e:
            logger.error(f"加载索引时出错: {e}. 创建新索引。")
            self._create_new_index()
            
    def _create_new_index(self):
        """创建新的空FAISS索引"""
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        # Consider using IndexIDMap if IDs are non-sequential or need mapping
        # self.index = faiss.IndexIDMap(faiss.IndexFlatL2(self.embedding_dim))
        self.paper_ids = []
        logger.info(f"Created new empty FAISS index with dimension {self.embedding_dim}.")

    def _save_index(self):
        """将FAISS索引和ID列表保存到磁盘"""
        try:
            if self.index is None:
                 logger.error("无法保存空索引")
                 return
            os.makedirs(self.data_dir, exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            with open(self.paper_ids_path, 'wb') as f:
                pickle.dump(self.paper_ids, f)
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors and {len(self.paper_ids)} IDs.")
        except Exception as e:
            logger.error(f"保存索引时出错: {e}")
    
    # Renamed generate_embedding to _embed_texts and made it async
    async def _embed_texts(self, texts: List[str]) -> Optional[List[np.ndarray]]:
        """
        使用 llm_service 生成文本列表的嵌入向量。
        现在这个方法只接收文本列表，分批逻辑移到调用者处。
        """
        if not texts:
             return []
             
        # 调用 llm_service (llm_service 内部处理 API 调用)
        embeddings = await llm_service.get_embeddings(
            texts=texts,
            model=self.embedding_model,
            # dimensions 不再传递，使用模型默认值
            # dimensions=self.embedding_dim 
        )
        
        if embeddings is None:
             logger.error(f"Failed to get embeddings for batch of {len(texts)} texts.")
             return None
             
        return [np.array(emb, dtype='float32') for emb in embeddings]

    async def add_papers(self, papers: List[Paper]):
        """
        将论文异步添加到索引 (使用外部API获取嵌入，并进行分批处理)
        """
        start_time = time.time()
        processed_paper_ids = set(self.paper_ids) # Use set for faster lookup
        
        texts_to_embed = []
        paper_ids_for_texts = [] # Keep track of IDs corresponding to texts

        # 1. Filter out papers already in index and prepare texts
        for paper in papers:
            if paper.paper_id not in processed_paper_ids:
                text = f"{paper.title} {paper.abstract or ''}".strip()
                if text: 
                     texts_to_embed.append(text)
                     paper_ids_for_texts.append(paper.paper_id)
                else:
                     logger.warning(f"Paper {paper.paper_id} has no text to embed. Skipping.")
                     
        if not texts_to_embed:
            logger.info("没有新的、包含文本的论文需要添加到索引")
            return

        total_texts_to_process = len(texts_to_embed)
        logger.info(f"准备为 {total_texts_to_process} 篇新论文获取嵌入向量，批大小: {self.embedding_batch_size}...")
        
        all_new_embeddings = []
        successfully_embedded_ids = []
        batches_processed = 0
        failed_batches = 0

        # 2. Get embeddings in batches
        for i in range(0, total_texts_to_process, self.embedding_batch_size):
            batch_texts = texts_to_embed[i : i + self.embedding_batch_size]
            batch_ids = paper_ids_for_texts[i : i + self.embedding_batch_size]
            batches_processed += 1
            
            logger.debug(f"  处理批次 {batches_processed}, 数量: {len(batch_texts)}")
            batch_embeddings = await self._embed_texts(batch_texts)
            
            if batch_embeddings is not None and len(batch_embeddings) == len(batch_texts):
                 all_new_embeddings.extend(batch_embeddings)
                 successfully_embedded_ids.extend(batch_ids)
                 logger.debug(f"    批次 {batches_processed} 嵌入成功.")
                 # Optional: Add a small delay between batches if rate limits are hit
                 await asyncio.sleep(0.2) 
            else:
                 failed_batches += 1
                 logger.error(f"    批次 {batches_processed} (IDs: {batch_ids}) 嵌入失败或返回数量不匹配. 跳过此批次。")
                 # Decide if you want to stop the whole process on one batch failure
                 # continue 

        if not all_new_embeddings:
             logger.error("所有批次的嵌入请求均失败。无法向索引添加新论文。")
             return
             
        logger.info(f"所有批次处理完成。成功获取 {len(all_new_embeddings)}/{total_texts_to_process} 个嵌入向量。失败批次数: {failed_batches}")

        # 3. Add successfully embedded vectors and IDs to index
        try:
             embeddings_array = np.array(all_new_embeddings).astype('float32')
             if embeddings_array.ndim != 2 or embeddings_array.shape[0] == 0:
                  logger.error("最终嵌入向量数组格式不正确或为空，无法添加到索引。")
                  return
             if embeddings_array.shape[1] != self.embedding_dim:
                  logger.error(f"Received embedding dimension ({embeddings_array.shape[1]}) does not match index dimension ({self.embedding_dim}). Aborting add.")
                  return
                  
             self.index.add(embeddings_array)
             self.paper_ids.extend(successfully_embedded_ids)
             
             # 4. Save the updated index
             self._save_index()
             duration = time.time() - start_time
             logger.info(f"成功添加 {len(successfully_embedded_ids)} 篇新论文到索引. 总数: {self.index.ntotal}. 失败批次数: {failed_batches}. 总耗时: {duration:.2f} 秒.")
             
        except Exception as e:
            logger.error(f"向索引添加向量或保存时出错: {e}")
            # Rollback might be complex here, as index might be partially updated
            # Best approach might be logging and manual check/rebuild if needed
            raise
    
    # Made search async
    async def search(self, query: str, k: int = 10) -> List[str]:
        """
        通过查询异步搜索论文 (查询通常是单个文本，不需要分批)
        """
        try:
            if self.index is None or self.index.ntotal == 0:
                logger.warning("尝试搜索空索引或未初始化的索引")
                return []
            
            # 1. Get query embedding (for a single query text)
            query_embedding_list = await self._embed_texts([query])
            
            if not query_embedding_list or query_embedding_list[0] is None:
                 logger.error(f"无法为查询生成嵌入向量: '{query}'")
                 return []
                 
            query_embedding = query_embedding_list[0].reshape(1, -1) 
            
            if query_embedding.shape[1] != self.embedding_dim:
                 logger.error(f"Query embedding dimension ({query_embedding.shape[1]}) does not match index dimension ({self.embedding_dim}).")
                 return []
                 
            # 2. Search index
            k_actual = min(k, self.index.ntotal) 
            distances, indices = self.index.search(query_embedding, k_actual)
            
            # 3. Get paper IDs
            if indices.size == 0 or len(indices[0]) == 0: # Check if search returned any results
                 return []
                 
            result_ids = [self.paper_ids[idx] for idx in indices[0] if idx >= 0 and idx < len(self.paper_ids)] 
            
            logger.debug(f"Search for '{query}' found {len(result_ids)} results (k={k}).")
            return result_ids
            
        except Exception as e:
            logger.error(f"搜索索引时出错: {e}", exc_info=True)
            return []
            
    # search_by_vector remains synchronous as it doesn't need async embedding call
    def search_by_vector(self, vector: np.ndarray, k: int = 10) -> Tuple[List[float], List[str]]:
        """
        使用预计算的向量搜索索引。
        
        Args:
            vector: 查询向量 (numpy array, float32)。
            k: 返回结果数量。
        
        Returns:
            一个元组 (距离列表, 论文ID列表)。
        """
        if self.index is None or self.index.ntotal == 0:
            return [], []
            
        vector_np = vector.reshape(1, -1).astype('float32')
        if vector_np.shape[1] != self.embedding_dim:
             logger.error(f"Search vector dimension ({vector_np.shape[1]}) does not match index dimension ({self.embedding_dim}).")
             return [], []
             
        k_actual = min(k, self.index.ntotal)
        distances, indices = self.index.search(vector_np, k_actual)
        
        if len(indices[0]) == 0:
             return [], []
             
        result_ids = [self.paper_ids[idx] for idx in indices[0] if idx >= 0 and idx < len(self.paper_ids)]
        result_distances = distances[0].tolist()
        
        return result_distances, result_ids

# 创建全局实例
vector_search_service = VectorSearchService() 