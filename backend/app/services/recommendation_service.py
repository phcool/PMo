import logging
from typing import List, Dict, Any, Set, Optional, Tuple
from datetime import datetime, timedelta # Import timedelta
import numpy as np # Import numpy
import random
import math # Import math for time decay

from app.models.paper import Paper, PaperResponse # PaperResponse also needs to be imported if recommend_papers returns it
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service
from app.services.llm_service import llm_service # Needed for embedding model info

logger = logging.getLogger(__name__)

# --- Constants for weighting and decay --- 
VIEWED_PAPER_WEIGHT = 2.0
SEARCH_QUERY_WEIGHT = 1.0
TIME_DECAY_HALFLIFE_DAYS = 14 # Interest halves every 14 days
# -----------------------------------------

class RecommendationService:
    """Recommendation service - Using weighted vector profiles, hybrid strategies and reranking for personalized recommendations"""
    
    async def build_user_profile(
        self,
        user_id: str,
        search_limit: int = 30, # Increased limit slightly
        view_limit: int = 20   # Increased limit slightly
    ) -> Tuple[Optional[np.ndarray], Dict[str, float]]:
        """
        Build a weighted user interest profile vector and preferred categories.

        Args:
            user_id: User ID
            search_limit: Number of recent search records to use
            view_limit: Number of recent view records to use

        Returns:
            A tuple: (user weighted profile vector, user preferred categories dict {category: weight}).
            Returns (None, {}) if profile cannot be built.
        """
        profile_items = [] # List of (text, weight, timestamp)
        preferred_categories = {} # {category: total_weight}
        now = datetime.now()

        # 1. Get user search history and calculate weights
        try:
            search_history = await db_service.get_search_history(user_id, limit=search_limit)
            if search_history and search_history.searches:
                for item in search_history.searches:
                    days_diff = (now - item.timestamp).total_seconds() / (24 * 3600)
                    # Exponential decay: weight = base_weight * (0.5 ^ (days / halflife))
                    time_weight = SEARCH_QUERY_WEIGHT * math.pow(0.5, days_diff / TIME_DECAY_HALFLIFE_DAYS)
                    if time_weight > 0.01: # Ignore very old interactions
                         profile_items.append((item.query, time_weight, item.timestamp))
        except Exception as e:
            logger.error(f"Error getting search history for user {user_id}: {e}")

        # 2. Get user viewing history and calculate weights
        try:
            viewed_papers = await db_service.get_viewed_papers(user_id, limit=view_limit)
            if viewed_papers:
                # Need timestamps for viewed papers - Assuming get_viewed_papers can provide this
                # Let's fetch full view history for timestamps
                user_views = await db_service.get_user_paper_views(user_id, limit=view_limit * 2) # Fetch more to ensure we get timestamps for viewed papers
                view_timestamps = {view.paper_id: view.last_viewed_at for view in user_views.views} if user_views else {}
                
                for paper in viewed_papers:
                    timestamp = view_timestamps.get(paper.paper_id, now - timedelta(days=TIME_DECAY_HALFLIFE_DAYS)) # Default to half-life age if no timestamp
                    days_diff = (now - timestamp).total_seconds() / (24 * 3600)
                    time_weight = VIEWED_PAPER_WEIGHT * math.pow(0.5, days_diff / TIME_DECAY_HALFLIFE_DAYS)
                    
                    if time_weight > 0.01:
                        # Add title and abstract text with calculated weight
                        profile_items.append((paper.title, time_weight, timestamp))
                        if paper.abstract:
                            profile_items.append((paper.abstract[:500], time_weight * 0.8, timestamp)) # Abstract slightly less weight than title
                        
                        # Update preferred categories weight
                        for category in paper.categories:
                            preferred_categories[category] = preferred_categories.get(category, 0) + time_weight
                            
        except Exception as e:
            logger.error(f"Error getting or processing view history for user {user_id}: {e}", exc_info=True)

        if not profile_items:
            logger.info(f"User {user_id} doesn't have enough recent history to build a profile vector")
            return None, {}

        # 3. Batch get embeddings for all texts
        texts_to_embed = [item[0] for item in profile_items]
        try:
            # Use the batch embedding method from vector_search_service
            # (Assuming _embed_texts exists and handles API calls)
            embeddings_list = await vector_search_service._embed_texts(texts_to_embed)
            
            if embeddings_list is None or len(embeddings_list) != len(profile_items):
                 logger.warning(f"Failed to generate enough embeddings for user {user_id}'s {len(profile_items)} profile texts")
                 return None, {}
                 
        except Exception as e:
            logger.error(f"Error getting embeddings for user {user_id}'s profile texts: {e}")
            return None, {}

        # 4. Calculate weighted average vector
        total_weight = 0
        weighted_sum_vector = np.zeros(vector_search_service.embedding_dim, dtype=np.float32)
        
        for i, item in enumerate(profile_items):
             text, weight, timestamp = item
             if i < len(embeddings_list) and embeddings_list[i] is not None:
                  embedding = embeddings_list[i]
                  weighted_sum_vector += embedding * weight
                  total_weight += weight
             else:
                  logger.warning(f"Skipping item due to missing embedding: {text[:50]}...")

        if total_weight > 0:
            profile_vector = (weighted_sum_vector / total_weight).astype(np.float32)
            # Normalize preferred category weights (optional, but good practice)
            total_cat_weight = sum(preferred_categories.values())
            if total_cat_weight > 0:
                 for cat in preferred_categories:
                      preferred_categories[cat] /= total_cat_weight
                      
            logger.info(f"Successfully built weighted profile vector for user {user_id} with {len(preferred_categories)} preferred categories")
            return profile_vector, preferred_categories
        else:
            logger.warning(f"Failed to calculate a valid weighted profile vector (total weight is 0)")
            return None, {}

    async def recommend_papers(self, user_id: str, limit: int = 10, offset: int = 0) -> List[PaperResponse]:
        """
        Get personalized paper recommendations (hybrid strategy + reranking)
        
        Args:
            user_id: User ID
            limit: Number of recommended papers to return
            offset: Pagination offset for loading more
            
        Returns:
            List of recommended papers
        """
        # 1. Build user profile
        profile_vector, preferred_categories = await self.build_user_profile(user_id)
        
        if profile_vector is None:
            logger.info(f"Unable to generate profile for user {user_id}, cannot provide personalized recommendations")
            return [] # API layer will handle random recommendations

        # --- 2. Candidate generation --- 
        candidate_papers: Dict[str, Dict[str, Any]] = {} # {paper_id: {paper: Paper, score: float, source: str}}
        search_k = (limit + offset) * 4 # Increase Faiss candidate pool size to account for offset
        
        # 2.1 Faiss similarity search
        try:
            distances, similar_ids = vector_search_service.search_by_vector(profile_vector, k=search_k)
            if similar_ids:
                 similar_papers = await db_service.get_papers_by_ids(similar_ids)
                 paper_map = {p.paper_id: p for p in similar_papers}
                 for i, paper_id in enumerate(similar_ids):
                      if paper_id in paper_map:
                           # Score based on similarity (higher is better)
                           similarity_score = 1.0 / (1.0 + distances[i]) if distances[i] >= 0 else 0 
                           candidate_papers[paper_id] = {"paper": paper_map[paper_id], "score": similarity_score, "source": "faiss"}
                 logger.info(f"Faiss found {len(similar_ids)} similar candidate papers for user {user_id}")
        except Exception as e:
             logger.error(f"Faiss similarity search failed for user {user_id}: {e}")
             
        # 2.2 Global latest papers
        try:
             recent_limit = limit + offset # Get enough papers for offset
             recent_papers = await db_service.get_recent_papers(limit=recent_limit)
             for paper in recent_papers:
                  if paper.paper_id not in candidate_papers: # Avoid duplicates
                       candidate_papers[paper.paper_id] = {"paper": paper, "score": 0.1, "source": "recent"} # Lower base score
             logger.info(f"Retrieved {len(recent_papers)} global latest papers as candidates")
        except Exception as e:
             logger.error(f"Failed to retrieve global latest papers: {e}")

        if not candidate_papers:
             logger.warning(f"Failed to generate any candidate recommended papers for user {user_id}")
             return []
             
        # --- 3. Filtering --- 
        # 3.1 Filter read papers
        viewed_paper_ids = set()
        try:
            viewed_data = await db_service.get_user_paper_views(user_id, limit=100) # Fetch reasonable number of views
            if viewed_data:
                 viewed_paper_ids = {view.paper_id for view in viewed_data.views}
                 original_count = len(candidate_papers)
                 candidate_papers = {pid: data for pid, data in candidate_papers.items() if pid not in viewed_paper_ids}
                 filtered_count = original_count - len(candidate_papers)
                 if filtered_count > 0:
                      logger.info(f"Filtered {filtered_count} user read papers from candidate set for user {user_id}")
        except Exception as e:
             logger.error(f"Error filtering user {user_id} read papers: {e}")

        if not candidate_papers:
             logger.warning(f"Filtered read papers, no remaining candidate recommended papers for user {user_id}")
             return []
             
        # --- 4. Reranking --- 
        ranked_candidates = []
        now = datetime.now()
        
        # Calculate scores with boosts
        for paper_id, data in candidate_papers.items():
             paper = data["paper"]
             final_score = data["score"] # Start with base score (similarity or fixed)
             
             # Freshness boost (higher for newer papers, up to ~90 days)
             days_old = (now - paper.published_date).days if paper.published_date else 365
             freshness_boost = max(0, 1.0 - (days_old / 90.0)) * 0.3 # Max boost 0.3
             final_score += freshness_boost
             
             # Category preference boost
             category_boost = 0
             if preferred_categories:
                  for category in paper.categories:
                       category_boost += preferred_categories.get(category, 0) * 0.5 # Use normalized weight
             final_score += category_boost
             
             ranked_candidates.append({"id": paper_id, "score": final_score, "paper": paper})
             
        # Sort by final score (descending)
        ranked_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # --- 5. Diversified selection Top Limit --- 
        final_recommendations = []
        category_counts: Dict[str, int] = {} # Count selected categories
        max_per_category = max(1, limit // 3) # Limit papers from the same primary category
        
        for candidate in ranked_candidates:
             if len(final_recommendations) >= limit:
                  break # Reached limit
                  
             paper = candidate["paper"]
             primary_category = paper.categories[0] if paper.categories else "unknown"
             
             # Check diversity constraint
             if category_counts.get(primary_category, 0) < max_per_category:
                  final_recommendations.append(candidate)
                  category_counts[primary_category] = category_counts.get(primary_category, 0) + 1
             else:
                  # Skip this candidate due to category concentration
                  logger.debug(f"Skipping {paper.paper_id} due to category ({primary_category}) limit.")
                  
        # If not enough diverse papers, fill remaining slots from top ranked
        if len(final_recommendations) < limit:
             remaining_needed = limit - len(final_recommendations)
             existing_ids = {rec["id"] for rec in final_recommendations}
             for candidate in ranked_candidates:
                  if remaining_needed <= 0:
                       break
                  if candidate["id"] not in existing_ids:
                       final_recommendations.append(candidate)
                       remaining_needed -= 1
                       
        # --- 6. Format output --- 
        output_papers = []
        
        # Apply offset and limit for pagination
        paginated_recommendations = final_recommendations[offset:offset+limit]
        
        for item in paginated_recommendations:
             paper = item["paper"]
             output_papers.append(PaperResponse(
                 paper_id=paper.paper_id,
                 title=paper.title,
                 authors=paper.authors,
                 abstract=paper.abstract,
                 categories=paper.categories,
                 pdf_url=paper.pdf_url,
                 published_date=paper.published_date,
                 updated_at=paper.updated_date 
             ))
             
        logger.info(f"Generated {len(output_papers)} optimized personalized recommendations for user {user_id} (offset: {offset})")
        return output_papers

# Create global recommendation service instance
recommendation_service = RecommendationService() 