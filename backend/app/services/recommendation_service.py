import logging
from typing import List, Dict, Any, Set, Optional, Tuple
from datetime import datetime, timedelta # Import timedelta
import numpy as np # 导入 numpy
import random
import math # Import math for time decay

from app.models.paper import Paper, PaperResponse # PaperResponse 也需要导入，如果recommend_papers返回它
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
    """推荐服务 - 使用加权向量画像、混合策略和重排序进行个性化推荐"""
    
    async def build_user_profile(
        self,
        user_id: str,
        search_limit: int = 30, # Increased limit slightly
        view_limit: int = 20   # Increased limit slightly
    ) -> Tuple[Optional[np.ndarray], Dict[str, float]]:
        """
        构建用户加权兴趣画像向量和偏好分类。

        Args:
            user_id: 用户ID
            search_limit: 使用的最近搜索记录数量
            view_limit: 使用的最近浏览记录数量

        Returns:
            一个元组: (用户加权画像向量, 用户偏好分类字典 {category: weight})。
            如果无法构建则返回 (None, {})。
        """
        profile_items = [] # List of (text, weight, timestamp)
        preferred_categories = {} # {category: total_weight}
        now = datetime.now()

        # 1. 获取用户搜索历史并计算权重
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
            logger.error(f"获取用户 {user_id} 搜索历史时出错: {e}")

        # 2. 获取用户浏览历史并计算权重
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
            logger.error(f"获取用户 {user_id} 浏览历史或处理分类时出错: {e}", exc_info=True)

        if not profile_items:
            logger.info(f"用户 {user_id} 没有足够的近期历史记录来构建画像向量")
            return None, {}

        # 3. 批量获取所有文本的嵌入向量
        texts_to_embed = [item[0] for item in profile_items]
        try:
            # Use the batch embedding method from vector_search_service
            # (Assuming _embed_texts exists and handles API calls)
            embeddings_list = await vector_search_service._embed_texts(texts_to_embed)
            
            if embeddings_list is None or len(embeddings_list) != len(profile_items):
                 logger.warning(f"未能为用户 {user_id} 的 {len(profile_items)} 个画像文本生成足够嵌入向量")
                 return None, {}
                 
        except Exception as e:
            logger.error(f"为用户 {user_id} 的画像文本获取嵌入时出错: {e}")
            return None, {}

        # 4. 计算加权平均向量
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
                      
            logger.info(f"成功为用户 {user_id} 构建加权画像向量和 {len(preferred_categories)} 个偏好分类")
            return profile_vector, preferred_categories
        else:
            logger.warning(f"无法为用户 {user_id} 计算有效的加权画像向量 (总权重为0)")
            return None, {}

    async def recommend_papers(self, user_id: str, limit: int = 10, offset: int = 0) -> List[PaperResponse]:
        """
        获取个性化推荐论文 (混合策略 + 重排序)
        
        Args:
            user_id: 用户ID
            limit: 返回的推荐论文数量
            offset: 分页偏移量，用于加载更多功能
            
        Returns:
            推荐论文列表
        """
        # 1. 构建用户画像
        profile_vector, preferred_categories = await self.build_user_profile(user_id)
        
        if profile_vector is None:
            logger.info(f"无法为用户 {user_id} 生成画像，无法进行个性化推荐")
            return [] # API层将处理随机推荐

        # --- 2. 候选生成 --- 
        candidate_papers: Dict[str, Dict[str, Any]] = {} # {paper_id: {paper: Paper, score: float, source: str}}
        search_k = (limit + offset) * 4 # Increase Faiss candidate pool size to account for offset
        
        # 2.1 Faiss 相似度搜索
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
                 logger.info(f"Faiss 找到 {len(similar_ids)} 个相似候选论文 for user {user_id}")
        except Exception as e:
             logger.error(f"Faiss 相似度搜索失败 for user {user_id}: {e}")
             
        # 2.2 全局最新论文
        try:
             recent_limit = limit + offset # Get enough papers for offset
             recent_papers = await db_service.get_recent_papers(limit=recent_limit)
             for paper in recent_papers:
                  if paper.paper_id not in candidate_papers: # Avoid duplicates
                       candidate_papers[paper.paper_id] = {"paper": paper, "score": 0.1, "source": "recent"} # Lower base score
             logger.info(f"获取了 {len(recent_papers)} 篇全局最新论文作为候选")
        except Exception as e:
             logger.error(f"获取全局最新论文失败: {e}")

        if not candidate_papers:
             logger.warning(f"未能为用户 {user_id} 生成任何候选推荐论文")
             return []
             
        # --- 3. 过滤 --- 
        # 3.1 过滤已读论文
        viewed_paper_ids = set()
        try:
            viewed_data = await db_service.get_user_paper_views(user_id, limit=100) # Fetch reasonable number of views
            if viewed_data:
                 viewed_paper_ids = {view.paper_id for view in viewed_data.views}
                 original_count = len(candidate_papers)
                 candidate_papers = {pid: data for pid, data in candidate_papers.items() if pid not in viewed_paper_ids}
                 filtered_count = original_count - len(candidate_papers)
                 if filtered_count > 0:
                      logger.info(f"从候选集中过滤了 {filtered_count} 篇用户已读论文 for user {user_id}")
        except Exception as e:
             logger.error(f"过滤用户 {user_id} 已读论文时出错: {e}")

        if not candidate_papers:
             logger.warning(f"过滤已读后，没有剩余候选推荐论文 for user {user_id}")
             return []
             
        # --- 4. 重排序 --- 
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
        
        # --- 5. 多样化选择 Top Limit --- 
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
                       
        # --- 6. 格式化输出 --- 
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
             
        logger.info(f"为用户 {user_id} 生成了 {len(output_papers)} 条优化后的个性化推荐 (偏移量: {offset})")
        return output_papers

# 创建全局推荐服务实例
recommendation_service = RecommendationService() 