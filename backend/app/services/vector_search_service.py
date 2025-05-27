import os
import logging
import numpy as np
import faiss
import asyncio 
from typing import List, Optional
import pickle
from pathlib import Path
import json

from app.models.paper import Paper
from app.services.llm_service import llm_service 

logger = logging.getLogger(__name__)

class VectorSearchService:
    """using faiss to handle vector search"""
    
    def __init__(self):
        """
        Initialize vector search service
        """
        self.embedding_dim = llm_service.default_embedding_dimensions
             
        self.index = None
        self.paper_ids = []
        
        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.index_path = str(self.data_dir / "paper_index.faiss")
        self.paper_ids_path = str(self.data_dir / "paper_ids.pkl")
        
        logger.info(f"VectorSearchService initialized")
        
        self.load_index()
    
    def load_index(self):
        """Load FAISS index and ID list from disk if they exist"""
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.paper_ids_path):
                self.index = faiss.read_index(self.index_path)
               
                with open(self.paper_ids_path, 'rb') as f:
                    self.paper_ids = pickle.load(f)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors and {len(self.paper_ids)} IDs.")
                if self.index.ntotal != len(self.paper_ids):
                        logger.warning("Index vector count and ID count mismatch")
            else:
                self.create_new_index()
        except Exception as e:
            logger.error(f"Error loading index: {e}. Creating new index.")
            self.create_new_index()
            
    def create_new_index(self):
        """Create a new empty FAISS index"""
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.paper_ids = []
        logger.info(f"Created new empty FAISS index")

    def save_index(self):
        """Save FAISS index and ID list to disk"""
        try:
            if self.index is None:
                 logger.error("Cannot save empty index")
                 return
            os.makedirs(self.data_dir, exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            with open(self.paper_ids_path, 'wb') as f:
                pickle.dump(self.paper_ids, f)
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors and {len(self.paper_ids)} IDs.")
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    async def embed_texts(self, texts: List[str]) -> Optional[List[np.ndarray]]:
        """
        Generate embeddings for a list of texts using llm_service.
        """
        if not texts:
             return []
             
        embeddings = await llm_service.get_embeddings(
            texts=texts,
        )
        
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        if embeddings is None:
             return None
             
        return [np.array(emb, dtype='float32') for emb in embeddings]

    async def add_papers(self, papers: List[Paper]):
        """
        add papers to the index
        """
        processed_paper_ids = set(self.paper_ids) 
        
        texts_to_embed = []
        paper_ids_for_texts = [] 

        # filter out papers already in index and prepare texts
        for paper in papers:
            if paper.paper_id not in processed_paper_ids:
                text = f"{paper.title} {paper.abstract or ''}".strip()
                if text: 
                     texts_to_embed.append(text)
                     paper_ids_for_texts.append(paper.paper_id)
                else:
                     logger.warning(f"Paper {paper.paper_id} has no text to embed. Skipping.")
                     
        if not texts_to_embed:
            logger.info("No new papers to add to the index")
            return

        total_texts_to_process = len(texts_to_embed)
        logger.info(f"Preparing to get embeddings for {total_texts_to_process} new papers")
        
        all_embeddings = await self.embed_texts(texts_to_embed)

        if not all_embeddings:
            logger.error("embedding requests failed")
            return

        embeddings_array = np.array(all_embeddings).astype('float32')


        try:
            self.index.add(embeddings_array)
            self.paper_ids.extend(paper_ids_for_texts)
            self.save_index()
             
        except Exception as e:
            logger.error(f"Error adding vectors to index or saving: {e}")
            raise
    
    async def vector_search(self, query: str, k: int = 50) -> List[str]:
        """
        vector search by a certain query
        """
        try:
            if self.index is None or self.index.ntotal == 0:
                logger.warning("empty index!!!")
                return []
            
            # get query embedding
            query_embedding_list = await self.embed_texts([query])
            
            if not query_embedding_list or query_embedding_list[0] is None:
                 logger.error(f"Failed to get embedding for query: '{query}'")
                 return []
                 
            query_embedding = query_embedding_list[0].reshape(1, -1) 
                 
            scores , indices = self.index.search(query_embedding, k)
                 
            result_ids = {self.paper_ids[idx] for idx in indices[0] if idx >= 0 and idx < len(self.paper_ids)}
            
            logger.debug(f"Search query'{query}' found {len(result_ids)} results.")
            return result_ids
            
        except Exception as e:
            logger.error(f"Error searching index: {e}", exc_info=True)
            return []
        
    async def search(self, query:str, k: int = 50) -> List[str]:
            system_prmpt="""You are a professional information retrieval assistant, capable of generating 5 distinct queries based on the user's input sentence for subsequent vector search. These queries should meet the following requirements:
            Diversity and Uniqueness: Each query should expand on the core topic of the user's input from different angles or directions, avoiding high similarity or repetition.
            Relevance: All queries must be closely related to the user's input sentence to ensure that the retrieved content matches the user's needs accurately.
            Conciseness: Each query should be as concise and clear as possible, avoiding redundancy and complexity, to facilitate subsequent processing and searching.
            Semantic Clarity: The wording of the queries should be clear and accurate, avoiding ambiguity, to ensure they can be correctly understood and processed by the vector search system.
            Now, please generate 5 different queries based on the user's input sentence.
            IMPORTNAT:use phrase instead of long sentence. the answer must be json format with 5 character strings and index from 1 to 5, do not contain any other character
            """

            messages=[{"role":"system","content":system_prmpt},
                      {"role":"user","content":query}
                    ]
            response = await llm_service.get_conversation_completion(
                messages=messages,
                temperature=llm_service.conversation_temperature,
                max_tokens=llm_service.max_tokens,
                stream=False,    
                thinking=False
            )
            json_data=response.choices[0].message.content
            querys=json.loads(json_data)


            # Create a list of coroutines for all queries
            search_tasks = [self.vector_search(querys[q]) for q in querys]
            # Execute all searches in parallel
            results = await asyncio.gather(*search_tasks)
            # Combine all results
            result_ids = set().union(*results)
            return result_ids
                
vector_search_service = VectorSearchService() 