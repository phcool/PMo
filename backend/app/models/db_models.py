from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, Table, ForeignKey, ARRAY, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# 论文分类关联表
paper_categories = Table(
    'paper_categories',
    Base.metadata,
    Column('paper_id', String, ForeignKey('papers.paper_id'), primary_key=True),
    Column('category', String, ForeignKey('categories.name'), primary_key=True)
)

# 论文作者关联表
paper_authors = Table(
    'paper_authors',
    Base.metadata,
    Column('paper_id', String, ForeignKey('papers.paper_id'), primary_key=True),
    Column('author', String, ForeignKey('authors.name'), primary_key=True)
)

class DBPaper(Base):
    """论文数据库模型"""
    __tablename__ = "papers"
    
    paper_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    abstract = Column(Text, nullable=False)
    pdf_url = Column(String, nullable=False)
    published_date = Column(DateTime, nullable=False)
    updated_date = Column(DateTime, nullable=True)
    
    # 关系
    authors = relationship("DBAuthor", secondary=paper_authors, backref="papers")
    categories = relationship("DBCategory", secondary=paper_categories, backref="papers")
    analysis = relationship("DBPaperAnalysis", uselist=False, back_populates="paper", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Paper {self.paper_id}: {self.title}>"

class DBAuthor(Base):
    """论文作者数据库模型"""
    __tablename__ = "authors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    
    def __repr__(self):
        return f"<Author {self.name}>"

class DBCategory(Base):
    """论文分类数据库模型"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    
    def __repr__(self):
        return f"<Category {self.name}>"

class DBPaperAnalysis(Base):
    """论文PDF分析结果数据库模型"""
    __tablename__ = "paper_analysis"
    
    paper_id = Column(String, ForeignKey("papers.paper_id"), primary_key=True)
    summary = Column(Text, nullable=True)
    key_findings = Column(Text, nullable=True)
    contributions = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)  
    future_work = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    paper = relationship("DBPaper", back_populates="analysis")
    
    def __repr__(self):
        return f"<PaperAnalysis {self.paper_id}>" 