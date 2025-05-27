import arxiv
import logging
from typing import List, Optional
from datetime import datetime, date

from app.models.paper import Paper

logger = logging.getLogger(__name__)


class ArxivService:
    """fetching papers from arXiv"""

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
        Fetch papers from arXiv within a date range
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
            
            query = " AND ".join(query_parts)
            
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
                    updated_date=updated_date
                )
                papers.append(paper)
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching papers from arXiv: {e}")
            raise
        
arxiv_service = ArxivService()