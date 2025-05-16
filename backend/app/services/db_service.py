import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_, text
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from app.models.paper import Paper, PaperResponse
from app.models.db_models import DBPaper, DBAuthor, DBCategory, DBUserPreferences, DBUserSearchHistory, DBUserPaperView
from app.models.user import UserPreferences, SearchHistoryItem, UserSearchHistory, PaperViewItem, UserPaperViews
from app.db.database import get_async_db

logger = logging.getLogger(__name__)

class DBService:
    """
    PostgreSQL database service for storing and retrieving paper data
    """
    
    def __init__(self):
        """Initialize database service"""
        pass
    
    async def add_papers(self, papers: List[Paper]) -> List[str]:
        """
        Add papers to the database
        
        Args:
            papers: List of papers to add
            
        Returns:
            List of added paper IDs
        """
        if not papers:
            return []
            
        added_ids = []
        async for db in get_async_db():
            try:
                # Collect all author and category names
                all_author_names = set()
                all_category_names = set()
                
                papers_to_add = []
                
                # First check which papers need to be added and collect all authors and categories
                for paper in papers:
                    # Check if paper already exists
                    result = await db.execute(
                        select(DBPaper).where(DBPaper.paper_id == paper.paper_id)
                    )
                    existing_paper = result.scalars().first()
                    
                    if existing_paper:
                        continue
                    
                    # Collect author and category names
                    all_author_names.update(paper.authors)
                    all_category_names.update(paper.categories)
                    papers_to_add.append(paper)
                
                if not papers_to_add:
                    return []
                
                # Query all existing authors and categories at once
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
                
                # Create non-existing authors and categories at once
                authors_to_create = all_author_names - existing_authors.keys()
                if authors_to_create:
                    # Use VALUES clause to insert multiple authors at once
                    author_objects = [DBAuthor(name=name) for name in authors_to_create]
                    db.add_all(author_objects)
                    # Immediately commit author data to avoid conflicts in subsequent inserts
                    await db.flush()
                    
                    # Query again to get all authors, including newly created ones
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
                    
                    # Query again to get all categories, including newly created ones
                    result = await db.execute(
                        select(DBCategory).where(DBCategory.name.in_(all_category_names))
                    )
                    for category in result.scalars().all():
                        existing_categories[category.name] = category
                
                # Now add papers and their associations
                for paper in papers_to_add:
                    db_paper = DBPaper(
                        paper_id=paper.paper_id,
                        title=paper.title,
                        abstract=paper.abstract,
                        pdf_url=paper.pdf_url,
                        published_date=paper.published_date,
                        updated_date=paper.updated_date
                    )
                    
                    # Add author associations
                    for author_name in paper.authors:
                        db_paper.authors.append(existing_authors[author_name])
                    
                    # Add category associations
                    for category_name in paper.categories:
                        db_paper.categories.append(existing_categories[category_name])
                    
                    db.add(db_paper)
                    added_ids.append(paper.paper_id)
                
                await db.commit()
                logger.info(f"Added {len(added_ids)} papers to the database")
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to add papers: {e}")
                raise
            
        return added_ids
    
    async def get_paper_by_id(self, paper_id: str) -> Optional[Paper]:
        """
        Get paper by ID
        
        Args:
            paper_id: Paper ID
            
        Returns:
            Paper object or None (if not found)
        """
        logger.info(f"Looking up paper in database with ID: {paper_id}")
        
        if not paper_id:
            logger.warning("Attempted to get paper with empty ID")
            return None
            
        try:
            async for db in get_async_db():
                try:
                    result = await db.execute(
                        select(DBPaper)
                        .options(
                            selectinload(DBPaper.authors),
                            selectinload(DBPaper.categories)
                        )
                        .where(DBPaper.paper_id == paper_id)
                    )
                    db_paper = result.scalars().first()
                    
                    if not db_paper:
                        logger.warning(f"Paper with ID {paper_id} not found in database")
                        return None
                    
                    # Convert to API model
                    paper = Paper(
                        paper_id=db_paper.paper_id,
                        title=db_paper.title,
                        authors=[author.name for author in db_paper.authors],
                        abstract=db_paper.abstract,
                        categories=[category.name for category in db_paper.categories],
                        pdf_url=db_paper.pdf_url,
                        published_date=db_paper.published_date,
                        updated_date=db_paper.updated_date,
                        embedding=None  # Embedding stored in faiss
                    )
                    
                    logger.info(f"Found paper: {paper.title} (ID: {paper.paper_id}) with {len(paper.authors)} authors and {len(paper.categories)} categories")
                    return paper
                    
                except SQLAlchemyError as e:
                    logger.error(f"Database error when getting paper by ID {paper_id}: {str(e)}")
                    return None
        except Exception as e:
            logger.error(f"Unexpected error when getting paper by ID {paper_id}: {str(e)}", exc_info=True)
            return None
        
        logger.warning(f"Paper lookup completed with no result for ID: {paper_id}")
        return None
    
    async def get_papers_by_ids(self, paper_ids: List[str]) -> List[Paper]:
        """
        Get multiple papers by IDs
        
        Args:
            paper_ids: List of paper IDs
            
        Returns:
            List of paper objects
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
            
            # Convert to API model
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
                    embedding=None  # Embedding stored in faiss
                ))
        
        return papers
    
    async def get_recent_papers(self, limit: int = 30, offset: int = 0) -> List[PaperResponse]:
        """
        Get recent papers (with pagination)
        
        Args:
            limit: Maximum number of papers to return
            offset: Number of papers to skip
            
        Returns:
            List of PaperResponse objects
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
            
            # Convert to API model
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
    
    async def get_random_papers_by_category(self, categories: List[str], limit: int = 30, offset: int = 0) -> List[PaperResponse]:
        """
        Get random papers from specified categories
        
        Args:
            categories: List of category names
            limit: Maximum number of papers to return
            offset: Page offset
            
        Returns:
            List of PaperResponse objects
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
                    .order_by(func.random())  # Use database's random function
                    .offset(offset)  # Add offset support
                    .limit(limit)
                )
                
                result = await db.execute(stmt)
                # Use distinct() to avoid repeated papers due to multiple category associations
                db_papers = result.scalars().unique().all() 
                
                # Convert to API model
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
                logger.error(f"Error getting papers by category: {e}")
                # Optionally return an empty list or rethrow the exception
                return []
        
        return papers
    
    async def count_papers(self) -> int:
        """
        Count total papers in database
        
        Returns:
            Total paper count
        """
        async for db in get_async_db():
            result = await db.execute(select(func.count()).select_from(DBPaper))
            count = result.scalar_one()
            return count
        return 0

    # User preferences related methods
    async def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """
        Get user access records
        
        Args:
            user_id: User ID
            
        Returns:
            User access records or None (if not exist)
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
                ip_prefix=db_prefs.ip_prefix,
                last_visited_at=db_prefs.last_visited_at,
                created_at=db_prefs.created_at
            )
        
        return None
        
    async def save_user_preferences(self, user_prefs: UserPreferences) -> bool:
        """
        Save user access records
        
        Args:
            user_prefs: User access records
            
        Returns:
            Whether the records were successfully saved
        """
        async for db in get_async_db():
            try:
                # Query if user already exists
                result = await db.execute(
                    select(DBUserPreferences)
                    .where(DBUserPreferences.user_id == user_prefs.user_id)
                )
                existing_prefs = result.scalars().first()
                
                now = datetime.now()
                
                if existing_prefs:
                    # Update existing records
                    existing_prefs.ip_prefix = user_prefs.ip_prefix
                    existing_prefs.last_visited_at = now
                else:
                    # Create new records
                    db_prefs = DBUserPreferences(
                        user_id=user_prefs.user_id,
                        ip_prefix=user_prefs.ip_prefix,
                        last_visited_at=now,
                        created_at=now
                    )
                    db.add(db_prefs)
                
                await db.commit()
                logger.info(f"User access records saved: {user_prefs.user_id}")
                return True
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to save user access records: {e}")
                return False
        
        return False

    # User search history related methods
    async def save_search_history(self, user_id: str, query: str) -> bool:
        """
        Save user search history
        
        Args:
            user_id: User ID
            query: Search query
            
        Returns:
            Whether the records were successfully saved
        """
        async for db in get_async_db():
            try:
                # Create search history records
                search_history = DBUserSearchHistory(
                    user_id=user_id,
                    query=query,
                    timestamp=datetime.now()
                )
                db.add(search_history)
                
                # Limit search history to 20 records per user
                # Delete the oldest record
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
                logger.info(f"User search history saved: {user_id}, Query: {query}")
                return True
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to save user search history: {e}")
                return False
        
        return False
        
    async def get_search_history(self, user_id: str, limit: int = 30) -> UserSearchHistory:
        """
        Get user search history
        
        Args:
            user_id: User ID
            limit: Maximum return count
            
        Returns:
            User search history
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
                logger.error(f"Error getting user search history: {e}")
        
        return UserSearchHistory(
            user_id=user_id,
            searches=searches,
            updated_at=datetime.now() if searches else None
        )
        
    async def record_paper_view(self, user_id: str, paper_id: str) -> bool:
        """
        Record user paper viewing records
        
        Args:
            user_id: User ID
            paper_id: Paper ID
            
        Returns:
            Whether the records were successfully recorded
        """
        if not user_id or not paper_id:
            return False
            
        async for db in get_async_db():
            try:
                # Check if paper exists
                paper_result = await db.execute(
                    select(DBPaper).where(DBPaper.paper_id == paper_id)
                )
                paper = paper_result.scalars().first()
                
                if not paper:
                    logger.warning(f"Failed to record viewing record: Paper does not exist {paper_id}")
                    return False
                
                # Check if today already has a record of this user viewing this paper
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
                    # Update existing records
                    existing_view.view_count += 1
                    existing_view.last_viewed_at = datetime.now()
                else:
                    # Create new records
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
                logger.error(f"Failed to record user paper viewing record: {e}")
                return False
        
        return False
        
    async def get_user_paper_views(self, user_id: str, limit: int = 30, days: int = 30) -> UserPaperViews:
        """
        Get user paper viewing records
        
        Args:
            user_id: User ID
            limit: Maximum return count
            days: Only return records from the past how many days
            
        Returns:
            User paper viewing records
        """
        if not user_id:
            return UserPaperViews(user_id=user_id, views=[], updated_at=None)
            
        views = []
        from datetime import timedelta
        date_from = datetime.now().date() - timedelta(days=days)
        
        async for db in get_async_db():
            try:
                # Get user's recent viewing records and join table query paper title
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
                logger.error(f"Error getting user paper viewing records: {e}")
        
        return UserPaperViews(
            user_id=user_id,
            views=views,
            updated_at=datetime.now() if views else None
        )
    
    async def get_viewed_papers(self, user_id: str, limit: int = 30) -> List[Paper]:
        """Get user's recently viewed papers list"""
        papers = []
        
        async for db in get_async_db():
            try:
                # Get user's recently viewed paper ID list
                stmt = text("""
                    SELECT DISTINCT user_paper_views.paper_id, user_paper_views.last_viewed_at
                    FROM user_paper_views
                    WHERE user_paper_views.user_id = :user_id
                    ORDER BY user_paper_views.last_viewed_at DESC
                    LIMIT :limit
                """)
                
                result = await db.execute(stmt, {"user_id": user_id, "limit": limit})
                paper_ids = [row[0] for row in result.fetchall()]
                
                if not paper_ids:
                    return []
                
                # Get paper details
                papers = await self.get_papers_by_ids(paper_ids)
                # Keep the order consistent with the query results
                papers.sort(key=lambda p: paper_ids.index(p.paper_id))
                
            except Exception as e:
                logger.error(f"Error getting user's viewed papers: {e}")
                return []
                
        return papers

# Create a global instance
db_service = DBService() 