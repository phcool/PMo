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
