from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, Table, ForeignKey, ARRAY, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

# Paper category association table
paper_categories = Table(
    'paper_categories',
    Base.metadata,
    Column('paper_id', String, ForeignKey('papers.paper_id'), primary_key=True),
    Column('category', String, ForeignKey('categories.name'), primary_key=True)
)

# Paper author association table
paper_authors = Table(
    'paper_authors',
    Base.metadata,
    Column('paper_id', String, ForeignKey('papers.paper_id'), primary_key=True),
    Column('author', String, ForeignKey('authors.name'), primary_key=True)
)

class DBPaper(Base):
    """Paper database model"""
    __tablename__ = "papers"
    
    paper_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    abstract = Column(Text, nullable=False)
    pdf_url = Column(String, nullable=False)
    published_date = Column(DateTime, nullable=False)
    updated_date = Column(DateTime, nullable=True)
    
    # Relationships
    authors = relationship("DBAuthor", secondary=paper_authors, backref="papers")
    categories = relationship("DBCategory", secondary=paper_categories, backref="papers")
    
    def __repr__(self):
        return f"<Paper {self.paper_id}: {self.title}>"

class DBAuthor(Base):
    """Paper author database model"""
    __tablename__ = "authors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    
    def __repr__(self):
        return f"<Author {self.name}>"

class DBCategory(Base):
    """Paper category database model"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    
    def __repr__(self):
        return f"<Category {self.name}>"

# Modify user table name
class DBUserPreferences(Base):
    """User access records database model"""
    __tablename__ = "user"
    
    user_id = sa.Column(sa.String, primary_key=True, index=True)
    ip_prefix = sa.Column(sa.String, nullable=True, index=True)  # Store the first part of the user's IP
    last_visited_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now())  # Last visit time
    created_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now())
    
    def __repr__(self):
        return f"<UserVisit(user_id='{self.user_id}', ip_prefix='{self.ip_prefix}')>"

# Add user search history table
class DBUserSearchHistory(Base):
    """User search history database model"""
    __tablename__ = "user_search_history"
    
    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.String, nullable=False, index=True)
    query = sa.Column(sa.String, nullable=False)
    timestamp = sa.Column(sa.DateTime, nullable=False, default=sa.func.now())
    
    def __repr__(self):
        return f"<UserSearchHistory(id={self.id}, user_id='{self.user_id}', query='{self.query}')>"

# Add user paper viewing history table
class DBUserPaperView(Base):
    """User paper viewing history database model"""
    __tablename__ = "user_paper_views"
    
    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.String, nullable=False, index=True)
    paper_id = sa.Column(sa.String, ForeignKey("papers.paper_id"), nullable=False, index=True)
    view_date = sa.Column(sa.Date, nullable=False, index=True, default=sa.func.current_date())
    first_viewed_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now())
    last_viewed_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now())
    view_count = sa.Column(sa.Integer, nullable=False, default=1)
    
    # Relationships
    paper = relationship("DBPaper", backref="views")
    
    def __repr__(self):
        return f"<UserPaperView(user_id='{self.user_id}', paper_id='{self.paper_id}', view_date='{self.view_date}')>"