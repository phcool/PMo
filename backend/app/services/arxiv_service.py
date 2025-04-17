import arxiv
import logging
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
        max_results: int = 100
    ) -> List[Paper]:
        """
        Fetch recent papers from arXiv by categories
        
        Args:
            categories: List of arXiv categories
            max_results: Maximum number of results to return
            
        Returns:
            List of Paper objects
        """
        try:
            # Create the search query for categories
            category_query = " OR ".join([f"cat:{category}" for category in categories])
            
            # Get the client and search
            client = arxiv.Client()
            search = arxiv.Search(
                query=category_query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            # Fetch results
            results = list(client.results(search))
            
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