import os
import logging
import numpy as np
import faiss
from typing import List, Tuple, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import pickle

from app.models.paper import Paper

logger = logging.getLogger(__name__)

# 设置环境变量，指定使用国内镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 或者使用清华镜像：os.environ["HF_ENDPOINT"] = "https://mirrors.tuna.tsinghua.edu.cn/huggingface"

class VectorSearchService:
    """使用FAISS进行向量搜索的服务"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        初始化向量搜索服务
        
        Args:
            model_name: 要使用的句子转换器模型名称
        """
        # 使用国内镜像下载模型
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        self.index = None
        self.paper_ids = []
        self.index_path = "data/paper_index.faiss"
        self.paper_ids_path = "data/paper_ids.pkl"
        
        # 尝试加载现有索引
        self._load_index()
    
    def _load_index(self):
        """如果存在，则从磁盘加载FAISS索引"""
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.paper_ids_path):
                self.index = faiss.read_index(self.index_path)
                with open(self.paper_ids_path, 'rb') as f:
                    self.paper_ids = pickle.load(f)
                logger.info(f"加载了含有 {len(self.paper_ids)} 篇论文的索引")
            else:
                # 创建新索引
                self.index = faiss.IndexFlatL2(self.embedding_dim)
                logger.info("创建了新的FAISS索引")
        except Exception as e:
            logger.error(f"加载索引时出错: {e}")
            # 创建新索引
            self.index = faiss.IndexFlatL2(self.embedding_dim)
            self.paper_ids = []
    
    def _save_index(self):
        """将FAISS索引保存到磁盘"""
        try:
            os.makedirs("data", exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            with open(self.paper_ids_path, 'wb') as f:
                pickle.dump(self.paper_ids, f)
            logger.info(f"保存了含有 {len(self.paper_ids)} 篇论文的索引")
        except Exception as e:
            logger.error(f"保存索引时出错: {e}")
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        生成文本的嵌入向量
        
        Args:
            text: 要生成嵌入的文本
            
        Returns:
            嵌入向量
        """
        return self.model.encode(text)
    
    async def add_papers(self, papers: List[Paper]):
        """
        将论文添加到索引
        
        Args:
            papers: 要添加的论文列表
        """
        try:
            # 为没有嵌入向量的论文生成嵌入向量
            embeddings = []
            ids_to_add = []
            
            for paper in papers:
                # 检查论文是否已在索引中
                if paper.paper_id in self.paper_ids:
                    continue
                
                # 如果需要，生成嵌入向量
                if paper.embedding is None:
                    # 结合标题和摘要以获得更好的嵌入
                    text = f"{paper.title} {paper.abstract}"
                    paper.embedding = self.generate_embedding(text).tolist()
                
                embeddings.append(paper.embedding)
                ids_to_add.append(paper.paper_id)
            
            if not embeddings:
                logger.info("没有新论文要添加到索引")
                return
            
            # 添加到索引中
            embeddings_array = np.array(embeddings).astype('float32')
            self.index.add(embeddings_array)
            self.paper_ids.extend(ids_to_add)
            
            # 保存更新后的索引
            self._save_index()
            
            logger.info(f"已将 {len(embeddings)} 篇论文添加到索引中，总计: {len(self.paper_ids)}")
            
        except Exception as e:
            logger.error(f"向索引添加论文时出错: {e}")
            raise
    
    async def search(self, query: str, k: int = 10) -> List[str]:
        """
        通过查询搜索论文
        
        Args:
            query: 搜索查询
            k: 返回结果数量
            
        Returns:
            论文ID列表
        """
        try:
            if not self.index or self.index.ntotal == 0:
                logger.warning("索引中没有论文")
                return []
            
            # 生成查询嵌入
            query_embedding = self.generate_embedding(query).reshape(1, -1).astype('float32')
            
            # 搜索索引
            distances, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
            
            # 从索引获取论文ID
            result_ids = [self.paper_ids[idx] for idx in indices[0]]
            
            return result_ids
            
        except Exception as e:
            logger.error(f"搜索索引时出错: {e}")
            return []

# 创建全局实例
vector_search_service = VectorSearchService() 