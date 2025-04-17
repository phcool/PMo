from fastapi import APIRouter, HTTPException, Query, Depends, Body
from typing import List, Optional
import logging

from app.models.paper import PaperSearchRequest, PaperSearchResponse, PaperResponse
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=PaperSearchResponse)
async def search_papers(search_request: PaperSearchRequest):
    """
    使用向量搜索查找论文
    """
    try:
        # 获取与查询匹配的论文ID
        paper_ids = await vector_search_service.search(
            query=search_request.query,
            k=search_request.limit
        )
        
        if not paper_ids:
            return PaperSearchResponse(results=[], count=0)
        
        # 从数据库中获取论文详情
        papers = await db_service.get_papers_by_ids(paper_ids)
        
        # 如果指定了分类，则按分类筛选
        if search_request.categories:
            papers = [
                p for p in papers if any(
                    cat in p.categories for cat in search_request.categories
                )
            ]
        
        # 转换为响应模型
        paper_responses = [
            PaperResponse(
                paper_id=p.paper_id,
                title=p.title,
                authors=p.authors,
                abstract=p.abstract,
                categories=p.categories,
                pdf_url=p.pdf_url,
                published_date=p.published_date,
                updated_date=p.updated_date
            ) for p in papers
        ]
        
        return PaperSearchResponse(
            results=paper_responses,
            count=len(paper_responses)
        )
        
    except Exception as e:
        logger.error(f"搜索论文时出错: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"搜索论文时出错: {str(e)}"
        ) 