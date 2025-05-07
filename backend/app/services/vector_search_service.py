import os
import logging
import numpy as np
import faiss
import asyncio # Import asyncio
from typing import List, Tuple, Dict, Any, Optional
import pickle
from pathlib import Path
import time

from app.models.paper import Paper
from app.services.llm_service import llm_service # Import llm_service

logger = logging.getLogger(__name__)

class VectorSearchService:
    """Vector search service using FAISS and external embedding API"""
    
    def __init__(self):
        """
        Initialize vector search service
        """
        # Get embedding dimensions and service configuration (default values from llm_service)
        self.embedding_dim = llm_service.default_embedding_dimensions
        self.embedding_model = llm_service.default_embedding_model
        # Read embedding API batch size from environment variables, default is 10 (optimized for v3 models)
        self.embedding_batch_size = int(os.getenv("API_EMBEDDING_BATCH_SIZE", "10")) 
        
        if not self.embedding_dim:
             raise ValueError("Embedding dimension not configured in LLMService!")
             
        self.index = None
        self.paper_ids = []
        
        # Project root and data dir setup (remains the same)
        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.index_path = str(self.data_dir / "paper_index.faiss")
        self.paper_ids_path = str(self.data_dir / "paper_ids.pkl")
        
        logger.info(f"VectorSearchService initializing with {self.embedding_dim}-dim embeddings (Model: {self.embedding_model}, Batch Size: {self.embedding_batch_size})")
        logger.info(f"Index file path: {self.index_path}")
        
        # Load existing index or create a new one (remains mostly the same)
        self._load_index()
    
    def _load_index(self):
        """Load FAISS index and ID list from disk if they exist"""
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.paper_ids_path):
                self.index = faiss.read_index(self.index_path)
                # Check if loaded index dimension matches config
                if self.index.d != self.embedding_dim:
                     logger.warning(f"Loaded index dimension ({self.index.d}) does not match configured dimension ({self.embedding_dim}). Creating new index.")
                     self._create_new_index()
                else:
                    with open(self.paper_ids_path, 'rb') as f:
                        self.paper_ids = pickle.load(f)
                    logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors and {len(self.paper_ids)} IDs.")
                    if self.index.ntotal != len(self.paper_ids):
                         logger.warning("Index vector count and ID count mismatch! Rebuilding might be needed.")
            else:
                self._create_new_index()
        except Exception as e:
            logger.error(f"Error loading index: {e}. Creating new index.")
            self._create_new_index()
            
    def _create_new_index(self):
        """Create a new empty FAISS index"""
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        # Consider using IndexIDMap if IDs are non-sequential or need mapping
        # self.index = faiss.IndexIDMap(faiss.IndexFlatL2(self.embedding_dim))
        self.paper_ids = []
        logger.info(f"Created new empty FAISS index with dimension {self.embedding_dim}.")

    def _save_index(self):
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
    
    # Renamed generate_embedding to _embed_texts and made it async
    async def _embed_texts(self, texts: List[str]) -> Optional[List[np.ndarray]]:
        """
        Generate embeddings for a list of texts using llm_service.
        This method now only accepts a list of texts, batch logic moved to caller.
        """
        if not texts:
             return []
             
        # Call llm_service (llm_service handles API calls internally)
        embeddings = await llm_service.get_embeddings(
            texts=texts,
            model=self.embedding_model,
            # dimensions no longer passed, using model default
            # dimensions=self.embedding_dim 
        )
        
        if embeddings is None:
             logger.error(f"Failed to get embeddings for batch of {len(texts)} texts.")
             return None
             
        return [np.array(emb, dtype='float32') for emb in embeddings]

    async def add_papers(self, papers: List[Paper]):
        """
        Asynchronously add papers to the index (get embeddings from external API with batch processing)
        """
        start_time = time.time()
        processed_paper_ids = set(self.paper_ids) # Use set for faster lookup
        
        texts_to_embed = []
        paper_ids_for_texts = [] # Keep track of IDs corresponding to texts

        # 1. Filter out papers already in index and prepare texts
        for paper in papers:
            if paper.paper_id not in processed_paper_ids:
                text = f"{paper.title} {paper.abstract or ''}".strip()
                if text: 
                     texts_to_embed.append(text)
                     paper_ids_for_texts.append(paper.paper_id)
                else:
                     logger.warning(f"Paper {paper.paper_id} has no text to embed. Skipping.")
                     
        if not texts_to_embed:
            logger.info("No new papers with text to add to the index")
            return

        total_texts_to_process = len(texts_to_embed)
        logger.info(f"Preparing to get embeddings for {total_texts_to_process} new papers, batch size: {self.embedding_batch_size}...")
        
        all_new_embeddings = []
        successfully_embedded_ids = []
        batches_processed = 0
        failed_batches = 0

        # 2. Get embeddings in batches
        for i in range(0, total_texts_to_process, self.embedding_batch_size):
            batch_texts = texts_to_embed[i : i + self.embedding_batch_size]
            batch_ids = paper_ids_for_texts[i : i + self.embedding_batch_size]
            batches_processed += 1
            
            logger.debug(f"  Processing batch {batches_processed}, count: {len(batch_texts)}")
            batch_embeddings = await self._embed_texts(batch_texts)
            
            if batch_embeddings is not None and len(batch_embeddings) == len(batch_texts):
                 all_new_embeddings.extend(batch_embeddings)
                 successfully_embedded_ids.extend(batch_ids)
                 logger.debug(f"    Batch {batches_processed} embeddings successful.")
                 # Optional: Add a small delay between batches if rate limits are hit
                 await asyncio.sleep(0.2) 
            else:
                 failed_batches += 1
                 logger.error(f"    Batch {batches_processed} (IDs: {batch_ids}) embedding failed or returned mismatched count. Skipping this batch.")
                 # Decide if you want to stop the whole process on one batch failure
                 # continue 

        if not all_new_embeddings:
             logger.error("All embedding requests for all batches failed. Unable to add new papers to index.")
             return
             
        logger.info(f"All batches processed. Successfully obtained {len(all_new_embeddings)}/{total_texts_to_process} embeddings. Failed batches: {failed_batches}")

        # 3. Add successfully embedded vectors and IDs to index
        try:
             embeddings_array = np.array(all_new_embeddings).astype('float32')
             if embeddings_array.ndim != 2 or embeddings_array.shape[0] == 0:
                  logger.error("Final embedding array has incorrect format or is empty, cannot add to index.")
                  return
             if embeddings_array.shape[1] != self.embedding_dim:
                  logger.error(f"Received embedding dimension ({embeddings_array.shape[1]}) does not match index dimension ({self.embedding_dim}). Aborting add.")
                  return
                  
             self.index.add(embeddings_array)
             self.paper_ids.extend(successfully_embedded_ids)
             
             # 4. Save the updated index
             self._save_index()
             duration = time.time() - start_time
             logger.info(f"Successfully added {len(successfully_embedded_ids)} new papers to index. Total: {self.index.ntotal}. Failed batches: {failed_batches}. Total time: {duration:.2f} seconds.")
             
        except Exception as e:
            logger.error(f"Error adding vectors to index or saving: {e}")
            # Rollback might be complex here, as index might be partially updated
            # Best approach might be logging and manual check/rebuild if needed
            raise
    
    # Made search async
    async def search(self, query: str, k: int = 30) -> List[str]:
        """
        Asynchronously search for papers by query (query is typically a single text, no need for batching)
        """
        try:
            if self.index is None or self.index.ntotal == 0:
                logger.warning("Attempted to search an empty or uninitialized index")
                return []
            
            # 1. Get query embedding (for a single query text)
            query_embedding_list = await self._embed_texts([query])
            
            if not query_embedding_list or query_embedding_list[0] is None:
                 logger.error(f"Failed to get embedding for query: '{query}'")
                 return []
                 
            query_embedding = query_embedding_list[0].reshape(1, -1) 
            
            if query_embedding.shape[1] != self.embedding_dim:
                 logger.error(f"Query embedding dimension ({query_embedding.shape[1]}) does not match index dimension ({self.embedding_dim}).")
                 return []
                 
            # 2. Search index
            k_actual = min(k, self.index.ntotal) 
            distances, indices = self.index.search(query_embedding, k_actual)
            
            # 3. Get paper IDs
            if indices.size == 0 or len(indices[0]) == 0: # Check if search returned any results
                 return []
                 
            result_ids = [self.paper_ids[idx] for idx in indices[0] if idx >= 0 and idx < len(self.paper_ids)] 
            
            logger.debug(f"Search for '{query}' found {len(result_ids)} results (k={k}).")
            return result_ids
            
        except Exception as e:
            logger.error(f"Error searching index: {e}", exc_info=True)
            return []
            
    # search_by_vector remains synchronous as it doesn't need async embedding call
    def search_by_vector(self, vector: np.ndarray, k: int = 30) -> Tuple[List[float], List[str]]:
        """
        Search index using a pre-computed vector.
        
        Args:
            vector: Query vector (numpy array, float32).
            k: Number of results to return.
        
        Returns:
            A tuple (list of distances, list of paper IDs).
        """
        if self.index is None or self.index.ntotal == 0:
            return [], []
            
        vector_np = vector.reshape(1, -1).astype('float32')
        if vector_np.shape[1] != self.embedding_dim:
             logger.error(f"Search vector dimension ({vector_np.shape[1]}) does not match index dimension ({self.embedding_dim}).")
             return [], []
             
        k_actual = min(k, self.index.ntotal)
        distances, indices = self.index.search(vector_np, k_actual)
        
        if len(indices[0]) == 0:
             return [], []
             
        result_ids = [self.paper_ids[idx] for idx in indices[0] if idx >= 0 and idx < len(self.paper_ids)]
        result_distances = distances[0].tolist()
        
        return result_distances, result_ids

# Create global instance
vector_search_service = VectorSearchService() 