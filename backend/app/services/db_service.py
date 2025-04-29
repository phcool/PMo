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
from app.models.db_models import DBPaper, DBAuthor, DBCategory, DBPaperAnalysis, DBPaperExtractedText, DBUserPreferences, DBUserSearchHistory, DBUserPaperView
from app.models.user import UserPreferences, SearchHistoryItem, UserSearchHistory, PaperViewItem, UserPaperViews
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
    
    async def get_random_papers_by_category(self, categories: List[str], limit: int = 10, offset: int = 0) -> List[PaperResponse]:
        """
        从指定分类中随机获取论文
        
        Args:
            categories: 分类名称列表
            limit: 返回的最大论文数
            offset: 分页偏移量
            
        Returns:
            PaperResponse对象列表
        """
        papers = []
        if not categories:
            return papers
            
        async for db in get_async_db():
            try:
                stmt = (
                    select(DBPaper)
                    .join(DBPaper.categories)
                    .options(
                        selectinload(DBPaper.authors),
                        selectinload(DBPaper.categories)
                    )
                    .where(DBCategory.name.in_(categories))
                    .order_by(func.random())  # 使用数据库的随机函数
                    .offset(offset)  # 添加偏移量支持
                    .limit(limit)
                )
                
                result = await db.execute(stmt)
                # 使用 distinct() 避免因多分类关联导致重复论文
                db_papers = result.scalars().unique().all() 
                
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
            except Exception as e:
                logger.error(f"按分类随机获取论文时出错: {e}")
                # 可以选择返回空列表或重新抛出异常
                return []
        
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
                # Check if analysis exists
                result = await db.execute(select(DBPaperAnalysis).filter(DBPaperAnalysis.paper_id == analysis.paper_id))
                db_analysis = result.scalars().first()
                
                if db_analysis:
                    # Update existing analysis
                    db_analysis.summary = analysis.summary
                    db_analysis.key_findings = analysis.key_findings
                    db_analysis.contributions = analysis.contributions
                    db_analysis.methodology = analysis.methodology
                    db_analysis.limitations = analysis.limitations
                    db_analysis.future_work = analysis.future_work
                    db_analysis.keywords = analysis.keywords
                    db_analysis.updated_at = datetime.utcnow()
                    logger.info(f"更新论文分析: {analysis.paper_id}")
                else:
                    # Create new analysis
                    db_analysis = DBPaperAnalysis(
                        paper_id=analysis.paper_id,
                        summary=analysis.summary,
                        key_findings=analysis.key_findings,
                        contributions=analysis.contributions,
                        methodology=analysis.methodology,
                        limitations=analysis.limitations,
                        future_work=analysis.future_work,
                        keywords=analysis.keywords,
                        created_at=analysis.created_at or datetime.utcnow(), # Use provided or default
                        updated_at=datetime.utcnow()
                    )
                    db.add(db_analysis)
                    logger.info(f"创建新的论文分析: {analysis.paper_id}")
                
                await db.commit()
                return True
        
        except Exception as e:
            await db.rollback()
            logger.error(f"保存论文分析失败 {analysis.paper_id}: {e}")
            return False
        return False # Should not happen if get_async_db works

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
                    keywords=db_analysis.keywords,
                    created_at=db_analysis.created_at,
                    updated_at=db_analysis.updated_at
                )
        
        except Exception as e:
            logger.error(f"获取论文分析结果时出错：{e}")
            return None

    async def get_papers_without_analysis(self, limit: int = 10) -> List[Paper]:
        """
        获取未分析的论文
        
        Args:
            limit: 最大返回数量
            
        Returns:
            论文列表
        """
        papers = []
        async for db in get_async_db():
            # 查询没有关联分析的论文
            stmt = (
                select(DBPaper)
                .options(
                    selectinload(DBPaper.authors),
                    selectinload(DBPaper.categories)
                )
                .outerjoin(DBPaperAnalysis)
                .where(DBPaperAnalysis.paper_id == None)
                .limit(limit)
            )
            
            result = await db.execute(stmt)
            db_papers = result.scalars().all()
            
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

    # 用户偏好相关方法
    async def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """
        获取用户偏好设置
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户偏好设置或None（如果不存在）
        """
        async for db in get_async_db():
            result = await db.execute(
                select(DBUserPreferences)
                .where(DBUserPreferences.user_id == user_id)
            )
            db_prefs = result.scalars().first()
            
            if not db_prefs:
                return None
            
            return UserPreferences(
                user_id=db_prefs.user_id,
                preferences=db_prefs.preferences,
                created_at=db_prefs.created_at,
                updated_at=db_prefs.updated_at
            )
        
        return None
        
    async def save_user_preferences(self, user_prefs: UserPreferences) -> bool:
        """
        保存用户偏好设置
        
        Args:
            user_prefs: 用户偏好设置
            
        Returns:
            是否成功保存
        """
        async for db in get_async_db():
            try:
                # 查询用户偏好是否已存在
                result = await db.execute(
                    select(DBUserPreferences)
                    .where(DBUserPreferences.user_id == user_prefs.user_id)
                )
                existing_prefs = result.scalars().first()
                
                now = datetime.now()
                
                if existing_prefs:
                    # 更新现有记录
                    existing_prefs.preferences = user_prefs.preferences
                    existing_prefs.updated_at = now
                else:
                    # 创建新记录
                    db_prefs = DBUserPreferences(
                        user_id=user_prefs.user_id,
                        preferences=user_prefs.preferences,
                        created_at=now,
                        updated_at=now
                    )
                    db.add(db_prefs)
                
                await db.commit()
                logger.info(f"用户偏好设置已保存: {user_prefs.user_id}")
                return True
                
            except Exception as e:
                await db.rollback()
                logger.error(f"保存用户偏好设置失败: {e}")
                return False
        
        return False

    # 用户搜索历史相关方法
    async def save_search_history(self, user_id: str, query: str) -> bool:
        """
        保存用户搜索历史
        
        Args:
            user_id: 用户ID
            query: 搜索查询
            
        Returns:
            是否成功保存
        """
        async for db in get_async_db():
            try:
                # 创建搜索历史记录
                search_history = DBUserSearchHistory(
                    user_id=user_id,
                    query=query,
                    timestamp=datetime.now()
                )
                db.add(search_history)
                
                # 限制每个用户的搜索历史数量为20条
                # 删除最旧的记录
                stmt = (
                    select(DBUserSearchHistory)
                    .where(DBUserSearchHistory.user_id == user_id)
                    .order_by(DBUserSearchHistory.timestamp.desc())
                    .offset(20)
                )
                
                result = await db.execute(stmt)
                old_records = result.scalars().all()
                
                for record in old_records:
                    await db.delete(record)
                
                await db.commit()
                logger.info(f"用户搜索历史已保存: {user_id}, 查询: {query}")
                return True
                
            except Exception as e:
                await db.rollback()
                logger.error(f"保存用户搜索历史失败: {e}")
                return False
        
        return False
        
    async def get_search_history(self, user_id: str, limit: int = 10) -> UserSearchHistory:
        """
        获取用户搜索历史
        
        Args:
            user_id: 用户ID
            limit: 最大返回数量
            
        Returns:
            用户搜索历史
        """
        searches = []
        
        async for db in get_async_db():
            try:
                stmt = (
                    select(DBUserSearchHistory)
                    .where(DBUserSearchHistory.user_id == user_id)
                    .order_by(DBUserSearchHistory.timestamp.desc())
                    .limit(limit)
                )
                
                result = await db.execute(stmt)
                db_searches = result.scalars().all()
                
                for db_search in db_searches:
                    searches.append(
                        SearchHistoryItem(
                            query=db_search.query,
                            timestamp=db_search.timestamp
                        )
                    )
                
            except Exception as e:
                logger.error(f"获取用户搜索历史时出错: {e}")
        
        return UserSearchHistory(
            user_id=user_id,
            searches=searches,
            updated_at=datetime.now() if searches else None
        )
        
    async def record_paper_view(self, user_id: str, paper_id: str) -> bool:
        """
        记录用户论文浏览记录
        
        Args:
            user_id: 用户ID
            paper_id: 论文ID
            
        Returns:
            是否成功记录
        """
        if not user_id or not paper_id:
            return False
            
        async for db in get_async_db():
            try:
                # 检查论文是否存在
                paper_result = await db.execute(
                    select(DBPaper).where(DBPaper.paper_id == paper_id)
                )
                paper = paper_result.scalars().first()
                
                if not paper:
                    logger.warning(f"记录浏览记录失败：论文不存在 {paper_id}")
                    return False
                
                # 检查今天是否已经有该用户浏览该论文的记录
                today = datetime.now().date()
                view_stmt = (
                    select(DBUserPaperView)
                    .where(
                        DBUserPaperView.user_id == user_id,
                        DBUserPaperView.paper_id == paper_id,
                        DBUserPaperView.view_date == today
                    )
                )
                
                result = await db.execute(view_stmt)
                existing_view = result.scalars().first()
                
                if existing_view:
                    # 更新现有记录
                    existing_view.view_count += 1
                    existing_view.last_viewed_at = datetime.now()
                else:
                    # 创建新记录
                    new_view = DBUserPaperView(
                        user_id=user_id,
                        paper_id=paper_id,
                        view_date=today,
                        first_viewed_at=datetime.now(),
                        last_viewed_at=datetime.now(),
                        view_count=1
                    )
                    db.add(new_view)
                
                await db.commit()
                return True
                
            except Exception as e:
                await db.rollback()
                logger.error(f"记录用户论文浏览记录时出错: {e}")
                return False
        
        return False
        
    async def get_user_paper_views(self, user_id: str, limit: int = 20, days: int = 30) -> UserPaperViews:
        """
        获取用户论文浏览记录
        
        Args:
            user_id: 用户ID
            limit: 最大返回数量
            days: 只返回最近多少天的记录
            
        Returns:
            用户论文浏览记录
        """
        if not user_id:
            return UserPaperViews(user_id=user_id, views=[], updated_at=None)
            
        views = []
        from datetime import timedelta
        date_from = datetime.now().date() - timedelta(days=days)
        
        async for db in get_async_db():
            try:
                # 获取用户最近的浏览记录，并联表查询论文标题
                stmt = (
                    select(DBUserPaperView, DBPaper.title)
                    .join(DBPaper, DBUserPaperView.paper_id == DBPaper.paper_id)
                    .where(
                        DBUserPaperView.user_id == user_id,
                        DBUserPaperView.view_date >= date_from
                    )
                    .order_by(DBUserPaperView.last_viewed_at.desc())
                    .limit(limit)
                )
                
                result = await db.execute(stmt)
                for view_record, title in result:
                    views.append(
                        PaperViewItem(
                            paper_id=view_record.paper_id,
                            title=title,
                            view_date=view_record.view_date,
                            view_count=view_record.view_count,
                            first_viewed_at=view_record.first_viewed_at,
                            last_viewed_at=view_record.last_viewed_at
                        )
                    )
                
            except Exception as e:
                logger.error(f"获取用户论文浏览记录时出错: {e}")
        
        return UserPaperViews(
            user_id=user_id,
            views=views,
            updated_at=datetime.now() if views else None
        )
    
    async def get_viewed_papers(self, user_id: str, limit: int = 10) -> List[Paper]:
        """
        获取用户浏览过的论文
        
        Args:
            user_id: 用户ID
            limit: 最大返回数量
            
        Returns:
            论文列表
        """
        if not user_id:
            return []
            
        papers = []
        
        async for db in get_async_db():
            try:
                # 获取用户最近浏览的论文ID
                stmt = (
                    select(DBUserPaperView.paper_id, DBUserPaperView.last_viewed_at)
                    .where(DBUserPaperView.user_id == user_id)
                    .order_by(DBUserPaperView.last_viewed_at.desc())
                    .distinct()
                    .limit(limit)
                )
                
                result = await db.execute(stmt)
                paper_ids = [row[0] for row in result.all()]
                
                if not paper_ids:
                    return []
                
                # 获取论文详情
                papers = await self.get_papers_by_ids(paper_ids)
                
            except Exception as e:
                logger.error(f"获取用户浏览过的论文时出错: {e}")
        
        return papers

    async def save_or_update_extracted_text(self, paper_id: str, text: str, word_count: Optional[int] = None) -> bool:
        """
        保存或更新论文提取的文本内容和字数统计。
        
        Args:
            paper_id: 论文ID。
            text: 提取的文本内容。
            word_count: 估算的字数。
            
        Returns:
            True 如果成功，False 如果失败。
        """
        async for db in get_async_db():
            try:
                # 尝试获取现有记录
                result = await db.execute(
                    select(DBPaperExtractedText).filter(DBPaperExtractedText.paper_id == paper_id)
                )
                existing_record = result.scalars().first()
                
                if existing_record:
                    # 更新现有记录
                    existing_record.text = text
                    existing_record.word_count = word_count # Update word count
                    existing_record.updated_at = datetime.utcnow()
                    logger.info(f"更新论文 {paper_id} 的提取文本和字数 ({word_count})")
                else:
                    # 创建新记录
                    new_record = DBPaperExtractedText(
                        paper_id=paper_id,
                        text=text,
                        word_count=word_count, # Add word count
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_record)
                    logger.info(f"为论文 {paper_id} 创建新的提取文本记录 (字数: {word_count})")
                    
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"保存或更新论文 {paper_id} 的提取文本失败: {e}", exc_info=True)
                return False
        return False # Fallback

    async def get_extracted_text(self, paper_id: str) -> Optional[str]:
        """
        获取指定论文的提取文本内容。
        
        Args:
            paper_id: 论文ID。
            
        Returns:
            提取的文本字符串，如果未找到则返回 None。
        """
        async for db in get_async_db():
            try:
                result = await db.execute(
                    select(DBPaperExtractedText.text).filter(DBPaperExtractedText.paper_id == paper_id)
                )
                # scalars().first() 会直接返回第一列的第一个值，即文本内容
                text_content = result.scalars().first()
                return text_content
            except Exception as e:
                logger.error(f"获取论文 {paper_id} 的提取文本失败: {e}")
                return None
        return None # Fallback

# 创建一个全局实例
db_service = DBService() 