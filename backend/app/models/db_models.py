from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, Integer, Float, Table, ForeignKey, ARRAY, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

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
    keywords = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    paper = relationship("DBPaper", back_populates="analysis")
    
    def __repr__(self):
        return f"<PaperAnalysis {self.paper_id}>"

# 修改用户表名
class DBUserPreferences(Base):
    """用户访问记录数据库模型"""
    __tablename__ = "user"
    
    user_id = sa.Column(sa.String, primary_key=True, index=True)
    ip_prefix = sa.Column(sa.String, nullable=True, index=True)  # 存储用户IP的前一部分
    last_visited_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now())  # 最后访问时间
    created_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now())
    
    def __repr__(self):
        return f"<UserVisit(user_id='{self.user_id}', ip_prefix='{self.ip_prefix}')>"

# 添加用户搜索历史表
class DBUserSearchHistory(Base):
    """用户搜索历史数据库模型"""
    __tablename__ = "user_search_history"
    
    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.String, nullable=False, index=True)
    query = sa.Column(sa.String, nullable=False)
    timestamp = sa.Column(sa.DateTime, nullable=False, default=sa.func.now())
    
    def __repr__(self):
        return f"<UserSearchHistory(id={self.id}, user_id='{self.user_id}', query='{self.query}')>"

# 添加用户论文浏览历史表
class DBUserPaperView(Base):
    """用户论文浏览历史数据库模型"""
    __tablename__ = "user_paper_views"
    
    id = sa.Column(sa.Integer, primary_key=True, index=True)
    user_id = sa.Column(sa.String, nullable=False, index=True)
    paper_id = sa.Column(sa.String, ForeignKey("papers.paper_id"), nullable=False, index=True)
    view_date = sa.Column(sa.Date, nullable=False, index=True, default=sa.func.current_date())
    first_viewed_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now())
    last_viewed_at = sa.Column(sa.DateTime, nullable=False, default=sa.func.now(), onupdate=sa.func.now())
    view_count = sa.Column(sa.Integer, nullable=False, default=1)
    
    # 关系
    paper = relationship("DBPaper", backref="views")
    
    def __repr__(self):
        return f"<UserPaperView(user_id='{self.user_id}', paper_id='{self.paper_id}', view_date='{self.view_date}')>"