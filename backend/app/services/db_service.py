import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.models.paper import Paper, PaperResponse, PaperAnalysis, PaperAnalysisResponse
from app.models.db_models import DBPaper, DBAuthor, DBCategory, DBPaperAnalysis
from app.db.database import get_async_db

logger = logging.getLogger(__name__)

class DBService:
    """
    PostgreSQL数据库服务，用于存储和检索论文数据
    """
    
    def __init__(self):
        """初始化数据库服务"""
        pass
    
    async def add_papers(self, papers: List[Paper]) -> List[str]:
        """
        添加论文到数据库
        
        Args:
            papers: 要添加的论文列表
            
        Returns:
            添加的论文ID列表
        """
        if not papers:
            return []
            
        added_ids = []
        async for db in get_async_db():
            try:
                # 收集所有作者和分类名称
                all_author_names = set()
                all_category_names = set()
                
                papers_to_add = []
                
                # 首先检查哪些论文需要添加，并收集所有作者和分类
                for paper in papers:
                    # 检查论文是否已存在
                    result = await db.execute(
                        select(DBPaper).where(DBPaper.paper_id == paper.paper_id)
                    )
                    existing_paper = result.scalars().first()
                    
                    if existing_paper:
                        continue
                    
                    # 收集作者和分类名称
                    all_author_names.update(paper.authors)
                    all_category_names.update(paper.categories)
                    papers_to_add.append(paper)
                
                if not papers_to_add:
                    return []
                
                # 一次性查询所有已存在的作者和分类
                existing_authors = {}
                if all_author_names:
                    result = await db.execute(
                        select(DBAuthor).where(DBAuthor.name.in_(all_author_names))
                    )
                    for author in result.scalars().all():
                        existing_authors[author.name] = author
                
                existing_categories = {}
                if all_category_names:
                    result = await db.execute(
                        select(DBCategory).where(DBCategory.name.in_(all_category_names))
                    )
                    for category in result.scalars().all():
                        existing_categories[category.name] = category
                
                # 一次性创建不存在的作者和分类
                authors_to_create = all_author_names - existing_authors.keys()
                if authors_to_create:
                    # 使用VALUES子句一次性插入多个作者
                    author_objects = [DBAuthor(name=name) for name in authors_to_create]
                    db.add_all(author_objects)
                    # 立即提交作者数据，避免后续插入时的冲突
                    await db.flush()
                    
                    # 再次查询获取所有作者，包括新创建的
                    result = await db.execute(
                        select(DBAuthor).where(DBAuthor.name.in_(all_author_names))
                    )
                    for author in result.scalars().all():
                        existing_authors[author.name] = author
                
                categories_to_create = all_category_names - existing_categories.keys()
                if categories_to_create:
                    category_objects = [DBCategory(name=name) for name in categories_to_create]
                    db.add_all(category_objects)
                    await db.flush()
                    
                    # 再次查询获取所有分类，包括新创建的
                    result = await db.execute(
                        select(DBCategory).where(DBCategory.name.in_(all_category_names))
                    )
                    for category in result.scalars().all():
                        existing_categories[category.name] = category
                
                # 现在添加论文及其关联
                for paper in papers_to_add:
                    db_paper = DBPaper(
                        paper_id=paper.paper_id,
                        title=paper.title,
                        abstract=paper.abstract,
                        pdf_url=paper.pdf_url,
                        published_date=paper.published_date,
                        updated_date=paper.updated_date
                    )
                    
                    # 添加作者关联
                    for author_name in paper.authors:
                        db_paper.authors.append(existing_authors[author_name])
                    
                    # 添加分类关联
                    for category_name in paper.categories:
                        db_paper.categories.append(existing_categories[category_name])
                    
                    db.add(db_paper)
                    added_ids.append(paper.paper_id)
                
                await db.commit()
                logger.info(f"添加了 {len(added_ids)} 篇论文到数据库")
                
            except Exception as e:
                await db.rollback()
                logger.error(f"添加论文失败: {e}")
                raise
            
        return added_ids
    
    async def get_paper_by_id(self, paper_id: str) -> Optional[Paper]:
        """
        通过ID获取论文
        
        Args:
            paper_id: 论文ID
            
        Returns:
            论文对象或None（如果未找到）
        """
        async for db in get_async_db():
            result = await db.execute(
                select(DBPaper)
                .options(
                    selectinload(DBPaper.authors),
                    selectinload(DBPaper.categories),
                    selectinload(DBPaper.analysis)
                )
                .where(DBPaper.paper_id == paper_id)
            )
            db_paper = result.scalars().first()
            
            if not db_paper:
                return None
            
            # 转换为API模型
            return Paper(
                paper_id=db_paper.paper_id,
                title=db_paper.title,
                authors=[author.name for author in db_paper.authors],
                abstract=db_paper.abstract,
                categories=[category.name for category in db_paper.categories],
                pdf_url=db_paper.pdf_url,
                published_date=db_paper.published_date,
                updated_date=db_paper.updated_date,
                embedding=None  # 嵌入向量存储在faiss中
            )
        
        return None
    
    async def get_papers_by_ids(self, paper_ids: List[str]) -> List[Paper]:
        """
        通过ID列表获取多篇论文
        
        Args:
            paper_ids: 论文ID列表
            
        Returns:
            论文对象列表
        """
        papers = []
        async for db in get_async_db():
            result = await db.execute(
                select(DBPaper)
                .options(
                    selectinload(DBPaper.authors),
                    selectinload(DBPaper.categories)
                )
                .where(DBPaper.paper_id.in_(paper_ids))
            )
            db_papers = result.scalars().all()
            
            # 转换为API模型
            for db_paper in db_papers:
                papers.append(Paper(
                    paper_id=db_paper.paper_id,
                    title=db_paper.title,
                    authors=[author.name for author in db_paper.authors],
                    abstract=db_paper.abstract,
                    categories=[category.name for category in db_paper.categories],
                    pdf_url=db_paper.pdf_url,
                    published_date=db_paper.published_date,
                    updated_date=db_paper.updated_date,
                    embedding=None  # 嵌入向量存储在faiss中
                ))
        
        return papers
    
    async def get_recent_papers(self, limit: int = 10, offset: int = 0) -> List[PaperResponse]:
        """
        获取最近的论文（带分页）
        
        Args:
            limit: 返回的最大论文数
            offset: 要跳过的论文数
            
        Returns:
            PaperResponse对象列表
        """
        papers = []
        async for db in get_async_db():
            result = await db.execute(
                select(DBPaper)
                .options(
                    selectinload(DBPaper.authors),
                    selectinload(DBPaper.categories)
                )
                .order_by(DBPaper.published_date.desc())
                .offset(offset)
                .limit(limit)
            )
            db_papers = result.scalars().all()
            
            # 转换为API模型
            for db_paper in db_papers:
                papers.append(PaperResponse(
                    paper_id=db_paper.paper_id,
                    title=db_paper.title,
                    authors=[author.name for author in db_paper.authors],
                    abstract=db_paper.abstract,
                    categories=[category.name for category in db_paper.categories],
                    pdf_url=db_paper.pdf_url,
                    published_date=db_paper.published_date,
                    updated_date=db_paper.updated_date
                ))
        
        return papers
    
    async def count_papers(self) -> int:
        """
        计算数据库中的论文总数
        
        Returns:
            论文数量
        """
        async for db in get_async_db():
            result = await db.execute(select(func.count()).select_from(DBPaper))
            return result.scalar_one()
        
        return 0

    async def save_paper_analysis(self, analysis: PaperAnalysis) -> bool:
        """
        保存论文分析结果
        
        Args:
            analysis: 论文分析对象
            
        Returns:
            操作是否成功
        """
        try:
            async for db in get_async_db():
                # 首先检查论文是否存在
                result = await db.execute(
                    select(DBPaper).where(DBPaper.paper_id == analysis.paper_id)
                )
                db_paper = result.scalars().first()
                
                if not db_paper:
                    logger.error(f"保存分析结果失败：论文不存在 {analysis.paper_id}")
                    return False
                
                # 检查该论文是否已有分析结果
                result = await db.execute(
                    select(DBPaperAnalysis).where(DBPaperAnalysis.paper_id == analysis.paper_id)
                )
                existing_analysis = result.scalars().first()
                
                if existing_analysis:
                    # 更新现有分析
                    existing_analysis.summary = analysis.summary
                    existing_analysis.key_findings = analysis.key_findings
                    existing_analysis.contributions = analysis.contributions
                    existing_analysis.methodology = analysis.methodology
                    existing_analysis.limitations = analysis.limitations
                    existing_analysis.future_work = analysis.future_work
                    existing_analysis.updated_at = analysis.updated_at
                else:
                    # 创建新分析
                    db_analysis = DBPaperAnalysis(
                        paper_id=analysis.paper_id,
                        summary=analysis.summary,
                        key_findings=analysis.key_findings,
                        contributions=analysis.contributions,
                        methodology=analysis.methodology,
                        limitations=analysis.limitations,
                        future_work=analysis.future_work,
                        created_at=analysis.created_at,
                        updated_at=analysis.updated_at
                    )
                    db.add(db_analysis)
                
                await db.commit()
                logger.info(f"已保存论文分析结果：{analysis.paper_id}")
                return True
        
        except Exception as e:
            logger.error(f"保存论文分析结果时出错：{e}")
            return False

    async def get_paper_analysis(self, paper_id: str) -> Optional[PaperAnalysis]:
        """
        获取论文分析结果
        
        Args:
            paper_id: 论文ID
            
        Returns:
            论文分析对象或None（如果未找到）
        """
        try:
            async for db in get_async_db():
                result = await db.execute(
                    select(DBPaperAnalysis).where(DBPaperAnalysis.paper_id == paper_id)
                )
                db_analysis = result.scalars().first()
                
                if not db_analysis:
                    return None
                
                return PaperAnalysis(
                    paper_id=db_analysis.paper_id,
                    summary=db_analysis.summary,
                    key_findings=db_analysis.key_findings,
                    contributions=db_analysis.contributions,
                    methodology=db_analysis.methodology,
                    limitations=db_analysis.limitations,
                    future_work=db_analysis.future_work,
                    created_at=db_analysis.created_at,
                    updated_at=db_analysis.updated_at
                )
        
        except Exception as e:
            logger.error(f"获取论文分析结果时出错：{e}")
            return None

    async def get_papers_without_analysis(self, limit: int = 10) -> List[Paper]:
        """
        获取未进行分析的论文列表
        
        Args:
            limit: 返回结果数量限制
            
        Returns:
            未分析的论文列表
        """
        try:
            async for db in get_async_db():
                # 查询没有关联分析的论文
                result = await db.execute(
                    select(DBPaper)
                    .outerjoin(DBPaperAnalysis, DBPaper.paper_id == DBPaperAnalysis.paper_id)
                    .options(
                        selectinload(DBPaper.authors),
                        selectinload(DBPaper.categories)
                    )
                    .where(DBPaperAnalysis.paper_id == None)
                    .limit(limit)
                )
                db_papers = result.scalars().all()
                
                papers = []
                for db_paper in db_papers:
                    papers.append(Paper(
                        paper_id=db_paper.paper_id,
                        title=db_paper.title,
                        authors=[author.name for author in db_paper.authors],
                        abstract=db_paper.abstract,
                        categories=[category.name for category in db_paper.categories],
                        pdf_url=db_paper.pdf_url,
                        published_date=db_paper.published_date,
                        updated_date=db_paper.updated_date,
                        embedding=None
                    ))
                
                return papers
        
        except Exception as e:
            logger.error(f"获取未分析的论文时出错：{e}")
            return []

# 创建一个全局实例
db_service = DBService() 