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

# Create a global instance
db_service = DBService() 