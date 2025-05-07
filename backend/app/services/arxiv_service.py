import arxiv
import logging
import time
from datetime import datetime
from typing import List, Optional

from app.models.paper import Paper

logger = logging.getLogger(__name__)


class ArxivService:
    """Service for fetching papers from arXiv"""
    
    @staticmethod
    def _remove_timezone(dt):
        """
        移除日期时间对象的时区信息
        
        Args:
            dt: 带时区的日期时间对象
            
        Returns:
            不带时区的日期时间对象
        """
        if dt and dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt
    
    @staticmethod
    async def fetch_recent_papers(
        categories: List[str], 
        max_results: int = 100,
        offset: int = 0
    ) -> List[Paper]:
        """
        Fetch recent papers from arXiv by categories
        
        Args:
            categories: List of arXiv categories
            max_results: Maximum number of results to return
            offset: Number of results to skip (for pagination)
            
        Returns:
            List of Paper objects
        """
        try:
            logger.info(f"从arXiv获取论文，类别: {categories}, 数量: {max_results}, 开始位置: {offset}")
            
            # Create the search query for categories
            category_query = " OR ".join([f"cat:{category}" for category in categories])
            
            # Get the client
            client = arxiv.Client(
                page_size=100,  # 设置最大页面大小
                delay_seconds=3,  # 防止请求过于频繁，可能被限速
                num_retries=3  # 失败重试次数
            )
            
            # 创建搜索对象
            search = arxiv.Search(
                query=category_query,
                max_results=offset + max_results,  # 需要获取足够多以覆盖offset
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            # Fetch all results
            all_results = list(client.results(search))
            
            # 应用offset并限制数量
            if offset > 0 and offset < len(all_results):
                results = all_results[offset:offset + max_results]
                logger.info(f"应用偏移: 获取到 {len(all_results)} 篇论文, 截取 {offset} 到 {offset + len(results)}")
            else:
                # 如果offset为0或超出范围，直接取前max_results个
                results = all_results[:max_results]
                if offset > 0:
                    logger.warning(f"偏移量 {offset} 超出获取到的论文数量 {len(all_results)}")
            
            # Convert to Paper objects
            papers = []
            for result in results:
                # 处理日期时间，移除时区信息
                published_date = ArxivService._remove_timezone(result.published)
                updated_date = ArxivService._remove_timezone(result.updated)
                
                paper = Paper(
                    paper_id=result.get_short_id(),
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    categories=result.categories,
                    pdf_url=result.pdf_url,
                    published_date=published_date,
                    updated_date=updated_date,
                    embedding=None  # Embeddings will be added later
                )
                papers.append(paper)
                
            logger.info(f"已从arXiv获取 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"从arXiv获取论文时出错: {e}")
            raise
            
    @staticmethod
    async def fetch_paper_by_id(paper_id: str) -> Optional[Paper]:
        """
        Fetch a specific paper from arXiv by ID
        
        Args:
            paper_id: arXiv paper ID
            
        Returns:
            Paper object or None if not found
        """
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                id_list=[paper_id],
                max_results=1
            )
            
            results = list(client.results(search))
            if not results:
                return None
                
            result = results[0]
            # 处理日期时间，移除时区信息
            published_date = ArxivService._remove_timezone(result.published)
            updated_date = ArxivService._remove_timezone(result.updated)
            
            paper = Paper(
                paper_id=result.get_short_id(),
                title=result.title,
                authors=[author.name for author in result.authors],
                abstract=result.summary,
                categories=result.categories,
                pdf_url=result.pdf_url,
                published_date=published_date,
                updated_date=updated_date,
                embedding=None
            )
            
            return paper
            
        except Exception as e:
            logger.error(f"获取论文 {paper_id} 时出错: {e}")
            return None 