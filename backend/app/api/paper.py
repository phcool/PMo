from fastapi import APIRouter, HTTPException, Query, Depends, Path, Body, Header
from typing import List, Optional
import logging
from datetime import datetime

from app.models.paper import Paper, PaperResponse, PaperAnalysisResponse
from app.services.db_service import db_service
from app.services.arxiv_service import ArxivService
from app.services.scheduler_service import scheduler_service
from app.services.paper_analysis_service import paper_analysis_service
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[PaperResponse])
async def get_papers(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    获取最近的论文（带分页）
    """
    papers = await db_service.get_recent_papers(limit=limit, offset=offset)
    return papers


@router.get("/count")
async def count_papers():
    """
    获取数据库中的论文总数
    """
    count = await db_service.count_papers()
    return {"count": count}


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: str):
    """
    通过ID获取论文
    """
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # 获取论文分析结果
    analysis = await db_service.get_paper_analysis(paper_id)
    
    # 转换为响应模型
    response = PaperResponse(
        paper_id=paper.paper_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        categories=paper.categories,
        pdf_url=paper.pdf_url,
        published_date=paper.published_date,
        updated_at=paper.updated_date,
        analysis=PaperAnalysisResponse(
            paper_id=analysis.paper_id,
            summary=analysis.summary,
            key_findings=analysis.key_findings,
            contributions=analysis.contributions,
            methodology=analysis.methodology,
            limitations=analysis.limitations,
            future_work=analysis.future_work,
            keywords=analysis.keywords,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at
        ) if analysis else None
    )
    
    return response

@router.post("/{paper_id}/analyze")
async def analyze_paper(paper_id: str):
    """
    分析指定论文的PDF内容
    """
    # 检查论文是否存在
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 分析论文
    analysis = await paper_analysis_service.analyze_paper(paper_id)
    if not analysis:
        raise HTTPException(status_code=500, detail="分析论文失败")
    
    return {
        "status": "success",
        "message": "论文分析完成",
        "paper_id": paper_id,
        "timestamp": analysis.updated_at.isoformat()
    }

@router.get("/{paper_id}/analysis", response_model=PaperAnalysisResponse)
async def get_paper_analysis(paper_id: str):
    """
    获取论文的分析结果
    """
    # 检查论文是否存在
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 获取分析结果
    analysis = await db_service.get_paper_analysis(paper_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="未找到该论文的分析结果")
    
    return PaperAnalysisResponse(
        paper_id=analysis.paper_id,
        summary=analysis.summary,
        key_findings=analysis.key_findings,
        contributions=analysis.contributions,
        methodology=analysis.methodology,
        limitations=analysis.limitations,
        future_work=analysis.future_work,
        keywords=analysis.keywords,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at
    )

@router.post("/analyze-batch", status_code=202)
async def analyze_batch_papers():
    """
    启动批量论文分析任务
    """
    result = await paper_analysis_service.start_analysis_task()
    return result

@router.get("/recommend/")
async def get_recommended_papers(
    limit: int = Query(5, description="推荐论文数量"),
    offset: int = Query(0, description="推荐论文偏移量"),
    x_user_id: Optional[str] = Header(None, description="用户唯一标识")
):
    """
    获取基于用户画像的推荐论文，或为新用户提供热门分类的随机论文
    """
    recommended_papers = []
    
    if x_user_id:
        # 尝试获取个性化推荐
        recommended_papers = await recommendation_service.recommend_papers(user_id=x_user_id, limit=limit, offset=offset)
        
    # 如果没有个性化推荐结果 (可能是新用户或历史不足)
    if not recommended_papers:
        logger.info(f"用户 {x_user_id or '匿名'} 没有个性化推荐，提供热门分类随机推荐")
        popular_categories = ["cs.CV", "cs.AI", "cs.LG", "cs.CL"]  # 定义热门分类
        recommended_papers = await db_service.get_random_papers_by_category(categories=popular_categories, limit=limit, offset=offset)
        
    return recommended_papers 