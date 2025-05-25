import arxiv
import logging
from typing import List, Optional
from datetime import datetime, date

from app.models.paper import Paper

logger = logging.getLogger(__name__)


class ArxivService:
    """Service for fetching papers from arXiv"""

    def __init__(self):
        self.client = arxiv.Client(
            page_size=1000,
            delay_seconds=3,
            num_retries=3
        )

    def remove_timezone(self,dt):
        if dt and dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt
    
    async def fetch_papers(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        max_results: int = 10000
    ) -> List[Paper]:
        """
        Fetch papers from arXiv within a specified date range

        Args:
            start_date: Start date for the search (inclusive). If None, no start date limit
            end_date: End date for the search (inclusive). If None, no end date limit  
            max_results: Maximum number of results to fetch (default: 1000)

        Returns:
            List of Paper objects within the specified date range
        """
        try:
            # Build query string for date range
            query_parts = []
            
            if start_date:
                start_str = start_date.strftime("%Y%m%d")
                query_parts.append(f"submittedDate:[{start_str}0000 TO ")
                
            if end_date:
                end_str = end_date.strftime("%Y%m%d")
                if start_date:
                    query_parts[-1] += f"{end_str}2359]"
                else:
                    query_parts.append(f"submittedDate:[* TO {end_str}2359]")
            else:
                if start_date:
                    query_parts[-1] += "*]"
            
            # If no date range specified, search all papers
            query = " AND ".join(query_parts) if query_parts else "all:*"
            
            
            client = self.client
            
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            # Fetch all results
            results = list(client.results(search))
            
            
            # Convert to Paper objects
            papers = []
            for result in results:
                # Process datetime, remove timezone information
                published_date = self.remove_timezone(result.published)
                updated_date = self.remove_timezone(result.updated)
                
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
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching papers from arXiv: {e}")
            raise
            
    async def fetch_paper_by_id(self, paper_id: str) -> Optional[Paper]:
        """
        Fetch a specific paper from arXiv by ID
        
        Args:
            paper_id: arXiv paper ID
            
        Returns:
            Paper object or None if not found
        """
        try:
            client = self.client
            search = arxiv.Search(
                id_list=[paper_id],
                max_results=1
            )
            
            results = list(client.results(search))
            if not results:
                return None
                
            result = results[0]
            # Process datetime, remove timezone information
            published_date = self.remove_timezone(result.published)
            updated_date = self.remove_timezone(result.updated)
            
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
        
arxiv_service = ArxivService()