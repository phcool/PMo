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
        Remove timezone information from a datetime object
        
        Args:
            dt: Datetime object with timezone
            
        Returns:
            Datetime object without timezone
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
            logger.info(f"Fetching papers from arXiv, categories: {categories}, count: {max_results}, offset: {offset}")
            
            # Create the search query for categories
            category_query = " OR ".join([f"cat:{category}" for category in categories])
            
            # Get the client
            client = arxiv.Client(
                page_size=100,  # Set maximum page size
                delay_seconds=3,  # Prevent too frequent requests that might be rate-limited
                num_retries=3  # Number of retry attempts on failure
            )
            
            # Create search object
            search = arxiv.Search(
                query=category_query,
                max_results=offset + max_results,  # Need to fetch enough to cover the offset
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            # Fetch all results
            all_results = list(client.results(search))
            
            # Apply offset and limit count
            if offset > 0 and offset < len(all_results):
                results = all_results[offset:offset + max_results]
                logger.info(f"Applying offset: Retrieved {len(all_results)} papers, slicing from {offset} to {offset + len(results)}")
            else:
                # If offset is 0 or exceeds range, take the first max_results
                results = all_results[:max_results]
                if offset > 0:
                    logger.warning(f"Offset {offset} exceeds number of papers retrieved {len(all_results)}")
            
            # Convert to Paper objects
            papers = []
            for result in results:
                # Process datetime, remove timezone information
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
                
            logger.info(f"Retrieved {len(papers)} papers from arXiv")
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching papers from arXiv: {e}")
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
            # Process datetime, remove timezone information
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
            logger.error(f"Error fetching paper {paper_id}: {e}")
            return None 