import asyncio
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List
from app.models.paper import Paper
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service

class ArxivSearchService:
    def __init__(self):
        self.base_url = "https://export.arxiv.org/api/query"
        self.queue = asyncio.Queue()
        self.consumer_task = asyncio.create_task(self.consumer())

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
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending"
            }

            response = requests.get(self.base_url, params=params)
            response.raise_for_status()

            # Parse XML response
            root = ET.fromstring(response.text)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', namespace)

            paper_list = []

            for entry in entries:
                # Extract paper ID from the id field
                id_elem = entry.find('atom:id', namespace)
                paper_id = id_elem.text.split('/')[-1] if id_elem is not None else ""

                # Extract title
                title_elem = entry.find('atom:title', namespace)
                title = ' '.join(title_elem.text.strip().split()) if title_elem is not None else ""

                # Extract authors
                authors = []
                author_elems = entry.findall('atom:author', namespace)
                for author_elem in author_elems:
                    name_elem = author_elem.find('atom:name', namespace)
                    if name_elem is not None:
                        authors.append(name_elem.text.strip())

                # Extract abstract/summary
                summary_elem = entry.find('atom:summary', namespace)
                abstract = summary_elem.text.strip() if summary_elem is not None else ""

                # Extract categories
                categories = []
                category_elems = entry.findall('atom:category', namespace)
                for cat_elem in category_elems:
                    term = cat_elem.get('term')
                    if term:
                        categories.append(term)

                # Extract PDF URL
                pdf_url = ""
                link_elems = entry.findall('atom:link', namespace)
                for link_elem in link_elems:
                    if link_elem.get('type') == 'application/pdf':
                        pdf_url = link_elem.get('href', "")
                        break

                # Extract dates
                published_elem = entry.find('atom:published', namespace)
                published_date = None
                if published_elem is not None:
                    try:
                        published_date = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00')).replace(tzinfo=None)
                    except:
                        published_date = None

                updated_elem = entry.find('atom:updated', namespace)
                updated_date = None
                if updated_elem is not None:
                    try:
                        updated_date = datetime.fromisoformat(updated_elem.text.replace('Z', '+00:00')).replace(tzinfo=None)
                    except:
                        updated_date = None

                paper = Paper(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    categories=categories,
                    pdf_url=pdf_url,
                    published_date=published_date,
                    updated_date=updated_date,
                    embedding=None
                )
                paper_list.append(paper)

            await self.queue.put(paper_list)

            return paper_list
        except Exception as e:
            print(f"Error searching arXiv: {str(e)}")
            return []

arxivsearch_service = ArxivSearchService()