#!/usr/bin/env python
"""
Standalone script to fetch papers from arXiv.
This script is designed to be run as a cron job outside of the web server processes.
"""
import os
import sys
import asyncio
import logging
import time
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

# 批次大小：每次从arXiv获取的论文数量
BATCH_SIZE = int(os.getenv("FETCH_BATCH_SIZE", "100"))

# 总目标数量：希望获取的论文总数
TOTAL_MAX_RESULTS = int(os.getenv("FETCH_TOTAL_MAX_RESULTS", "1000"))

# 批次间延迟（秒）：避免频繁请求arXiv API
BATCH_DELAY = int(os.getenv("FETCH_BATCH_DELAY", "3"))

async def fetch_papers_batch(categories, skip, max_results):
    """获取一批论文，带有起始偏移量"""
    logger.info(f"获取第 {skip+1}-{skip+max_results} 篇论文...")
    try:
        papers = await ArxivService.fetch_recent_papers(
            categories=categories,
            max_results=max_results,
            offset=skip
        )
        return papers
    except Exception as e:
        logger.error(f"获取批次论文失败 (skip={skip}): {e}", exc_info=True)
        return []

async def fetch_papers():
    """使用分批获取的方式从arXiv获取论文，并存储到数据库和向量索引中"""
    start_time = datetime.now()
    logger.info(f"开始论文获取任务，时间: {start_time}，目标数量: {TOTAL_MAX_RESULTS}")
    
    total_fetched = 0
    total_added = 0
    all_added_ids = set()
    
    try:
        # 分批获取
        for batch_start in range(0, TOTAL_MAX_RESULTS, BATCH_SIZE):
            # 计算当前批次的大小
            current_batch_size = min(BATCH_SIZE, TOTAL_MAX_RESULTS - batch_start)
            
            # 获取一批论文
            batch_papers = await fetch_papers_batch(
                categories=DEFAULT_CATEGORIES,
                skip=batch_start,
                max_results=current_batch_size
            )
            
            if not batch_papers:
                logger.info(f"批次 {batch_start//BATCH_SIZE + 1} 没有返回任何论文，停止获取")
                break
                
            total_fetched += len(batch_papers)
            
            # 添加到数据库
            added_ids = await db_service.add_papers(batch_papers)
            
            # 如果有新添加的论文，更新向量索引
            if added_ids:
                papers_to_add = [p for p in batch_papers if p.paper_id in added_ids]
                await vector_search_service.add_papers(papers_to_add)
                
                all_added_ids.update(added_ids)
                total_added += len(added_ids)
                
                logger.info(f"批次 {batch_start//BATCH_SIZE + 1}: 获取 {len(batch_papers)} 篇论文，添加 {len(added_ids)} 篇新论文")
            else:
                logger.info(f"批次 {batch_start//BATCH_SIZE + 1}: 获取 {len(batch_papers)} 篇论文，没有新论文添加")
            
            # 如果已经获取了足够的论文或者这批次返回的少于请求的，就停止
            if total_fetched >= TOTAL_MAX_RESULTS or len(batch_papers) < current_batch_size:
                break
                
            # 在批次之间添加延迟，避免对arXiv API发送太多请求
            if batch_start + BATCH_SIZE < TOTAL_MAX_RESULTS:
                logger.info(f"等待 {BATCH_DELAY} 秒后继续获取下一批...")
                await asyncio.sleep(BATCH_DELAY)
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"获取任务完成，耗时 {duration:.2f} 秒。总共获取 {total_fetched} 篇论文，添加 {total_added} 篇新论文。")
        
    except Exception as e:
        logger.error(f"获取任务发生错误: {e}", exc_info=True)

async def main():
    """Main entry point."""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Log script start with a divider for readability in logs
    logger.info("=" * 80)
    logger.info("启动论文获取脚本")
    logger.info(f"配置: 批次大小={BATCH_SIZE}, 总目标数量={TOTAL_MAX_RESULTS}, 批次间延迟={BATCH_DELAY}秒")
    
    # Run the fetch job
    await fetch_papers()
    
    logger.info("论文获取脚本完成")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main()) 