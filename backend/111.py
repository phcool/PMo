import arxiv
import asyncio
from typing import List
from app.models.paper import Paper

client = arxiv.Client( 
        page_size=1000,
        delay_seconds=10.0,
        num_retries=5
        )

search = arxiv.Search(
            query="analyzing",
            max_results=10,
            sort_by=arxiv.SortCriterion.Relevance
        ) 

results=client.results(search)
for result in results:
    print(result.title)
    print(result.published)
    print("haha")

