"""
迁移脚本：将基于文件的数据迁移到PostgreSQL数据库中

此脚本读取现有的papers.json文件，并将数据导入到PostgreSQL数据库中。
"""

import os
import sys
import json
import asyncio
from datetime import datetime
import logging
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.paper import Paper
from app.services.db_service import db_service
from app.db.database import engine, Base, SessionLocal
from app.models.db_models import DBPaper, DBAuthor, DBCategory, paper_authors, paper_categories

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def migrate_data():
    """将JSON数据迁移到PostgreSQL数据库"""
    
    # 读取JSON文件
    papers_file = "data/papers.json"
    
    if not os.path.exists(papers_file):
        logger.error(f"文件不存在: {papers_file}")
        return
    
    try:
        with open(papers_file, 'r') as f:
            papers_data = json.load(f)
        
        logger.info(f"已从文件加载 {len(papers_data)} 篇论文")
        
        # 使用同步会话来避免并发问题
        session = SessionLocal()
        
        try:
            # 将数据转换为Paper对象
            all_authors = set()
            all_categories = set()
            paper_count = 0
            
            # 首先收集所有作者和分类
            for paper_id, paper_data in papers_data.items():
                # 添加所有作者
                for author in paper_data.get('authors', []):
                    all_authors.add(author)
                
                # 添加所有分类
                for category in paper_data.get('categories', []):
                    all_categories.add(category)
            
            # 插入所有作者（使用upsert避免冲突）
            for i in range(0, len(all_authors), 100):
                batch = list(all_authors)[i:i+100]
                for author in batch:
                    stmt = pg_insert(DBAuthor).values(name=author).on_conflict_do_nothing()
                    session.execute(stmt)
                session.commit()
                logger.info(f"已处理 {i+len(batch)}/{len(all_authors)} 位作者")
            
            # 插入所有分类（使用upsert避免冲突）
            for i in range(0, len(all_categories), 100):
                batch = list(all_categories)[i:i+100]
                for category in batch:
                    stmt = pg_insert(DBCategory).values(name=category).on_conflict_do_nothing()
                    session.execute(stmt)
                session.commit()
                logger.info(f"已处理 {i+len(batch)}/{len(all_categories)} 个分类")
            
            # 现在插入论文
            batch_size = 25  # 减小批量大小
            paper_list = list(papers_data.items())
            
            for i in range(0, len(paper_list), batch_size):
                batch = paper_list[i:i+batch_size]
                for paper_id, paper_data in batch:
                    # 确保日期是datetime对象
                    if isinstance(paper_data.get('published_date'), str):
                        paper_data['published_date'] = datetime.fromisoformat(paper_data['published_date'])
                    if paper_data.get('updated_date') and isinstance(paper_data.get('updated_date'), str):
                        paper_data['updated_date'] = datetime.fromisoformat(paper_data['updated_date'])
                    
                    # 首先插入论文主体
                    db_paper = DBPaper(
                        paper_id=paper_id,
                        title=paper_data.get('title', ''),
                        abstract=paper_data.get('abstract', ''),
                        pdf_url=paper_data.get('pdf_url', ''),
                        published_date=paper_data.get('published_date', datetime.now()),
                        updated_date=paper_data.get('updated_date')
                    )
                    
                    # 使用upsert
                    stmt = pg_insert(DBPaper).values(
                        paper_id=db_paper.paper_id,
                        title=db_paper.title,
                        abstract=db_paper.abstract,
                        pdf_url=db_paper.pdf_url,
                        published_date=db_paper.published_date,
                        updated_date=db_paper.updated_date
                    ).on_conflict_do_nothing()
                    session.execute(stmt)
                    
                    # 为作者创建关联
                    for author_name in paper_data.get('authors', []):
                        stmt = pg_insert(paper_authors).values(
                            paper_id=paper_id, 
                            author=author_name
                        ).on_conflict_do_nothing()
                        session.execute(stmt)
                    
                    # 为分类创建关联
                    for category_name in paper_data.get('categories', []):
                        stmt = pg_insert(paper_categories).values(
                            paper_id=paper_id, 
                            category=category_name
                        ).on_conflict_do_nothing()
                        session.execute(stmt)
                    
                    paper_count += 1
                
                session.commit()
                logger.info(f"已处理 {i+len(batch)}/{len(paper_list)} 篇论文")
            
            logger.info(f"数据迁移已完成，共处理 {paper_count} 篇论文")
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"迁移数据时出错: {e}")
        raise

async def main():
    """主函数"""
    try:
        # 等待一会，确保数据库连接已经建立
        await asyncio.sleep(1)
        
        # 迁移数据
        await migrate_data()
        
    except Exception as e:
        logger.error(f"执行迁移脚本时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 