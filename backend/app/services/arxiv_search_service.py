import asyncio
import arxiv
from typing import List
from app.models.paper import Paper
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service

class ArxivSearchService:
    def __init__(self):
        self.client = arxiv.Client(
            page_size=100,
            delay_seconds=3,
            num_retries=3
        )
        self.queue = asyncio.Queue()
        self.consumer_task = asyncio.create_task(self.consumer())

    def remove_timezone(self, dt):
        if dt and dt.tzinfo:
            return dt.replace(tzinfo=None)
        return dt

    async def consumer(self):
        while True:
            paper_list = await self.queue.get()
            try:
                await db_service.add_papers(paper_list)
                await vector_search_service.add_papers(paper_list)
            except Exception as e:
                print(f"Error processing papers: {str(e)}")
            finally:
                self.queue.task_done()

    async def search(self, query: str, max_results: int = 100) -> List[str]:
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )

            paper_list = []

            for result in self.client.results(search):
                paper = Paper(
                    paper_id=result.get_short_id(),
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    categories=result.categories,
                    pdf_url=result.pdf_url,
                    published_date=self.remove_timezone(result.published),
                    updated_date=self.remove_timezone(result.updated),
                    embedding=None
                )
                paper_list.append(paper)

            await self.queue.put(paper_list)

            return paper_list
        except Exception as e:
            print(f"Error searching arXiv: {str(e)}")
            return []

arxivsearch_service = ArxivSearchService()