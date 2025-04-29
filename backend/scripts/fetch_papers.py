#!/usr/bin/env python
"""
Standalone script to fetch papers from arXiv.
This script is designed to be run as a cron job outside of the web server processes.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'cron_fetch.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cron_fetch")

# Import our services
from app.services.arxiv_service import ArxivService
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service

# Default categories to fetch
DEFAULT_CATEGORIES = [
    # 核心机器学习和深度学习类别
    "cs.LG",   # 机器学习
    "cs.AI",   # 人工智能
    "cs.CV",   # 计算机视觉
    "cs.CL",   # 计算语言学/自然语言处理
    "cs.NE",   # 神经和进化计算
    "stat.ML", # 统计机器学习
    
    # 相关应用领域
    "cs.RO",   # 机器人学
    "cs.IR",   # 信息检索
    "cs.MM",   # 多媒体
    "cs.SD",   # 声音
    "cs.HC",   # 人机交互
    
    # 系统与算法
    "cs.DC",   # 分布式计算
    "cs.DS",   # 数据结构与算法
    "cs.DB",   # 数据库
    "cs.PL",   # 编程语言
    "cs.NA",   # 数值分析
    "cs.AR",   # 硬件架构
    
    # 其他相关领域
    "cs.GT",   # 博弈论
    "cs.CC",   # 计算复杂性
    "cs.NI",   # 网络与互联网架构
    "cs.CR",   # 密码学与安全
    "cs.SE"    # 软件工程
]

# Maximum number of papers to fetch per run
MAX_RESULTS = int(os.getenv("FETCH_MAX_RESULTS", "100"))

async def fetch_papers():
    """Fetch papers from arXiv and store them in database and vector index."""
    start_time = datetime.now()
    logger.info(f"Starting paper fetch job at {start_time}")
    
    try:
        # Fetch papers from arXiv
        papers = await ArxivService.fetch_recent_papers(
            categories=DEFAULT_CATEGORIES,
            max_results=MAX_RESULTS
        )
        
        if not papers:
            logger.info("No new papers found")
            return
            
        # Add papers to database
        added_ids = await db_service.add_papers(papers)
        
        # Add papers to vector search index
        if added_ids:
            papers_to_add = [p for p in papers if p.paper_id in added_ids]
            await vector_search_service.add_papers(papers_to_add)
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Fetch job completed in {duration:.2f} seconds. Fetched {len(papers)} papers, added {len(added_ids)} new papers.")
        
    except Exception as e:
        logger.error(f"Error in fetch job: {e}", exc_info=True)

async def main():
    """Main entry point."""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Log script start with a divider for readability in logs
    logger.info("=" * 80)
    logger.info("Starting paper fetch script")
    
    # Run the fetch job
    await fetch_papers()
    
    logger.info("Paper fetch script completed")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main()) 