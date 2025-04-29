#!/usr/bin/env python
"""
Standalone script to analyze papers that have been previously fetched.
This script is designed to be run as a cron job outside of the web server processes.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
import time
import argparse

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'cron_analyze.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cron_analyze")

# Import our services
from app.services.paper_analysis_service import paper_analysis_service

async def analyze_papers(process_all=True, max_papers=None):
    """
    Analyze papers that haven't been analyzed yet.
    
    Args:
        process_all: 是否处理所有待分析论文
        max_papers: 最大处理论文数量
    """
    start_time = datetime.now()
    logger.info(f"Starting paper analysis job at {start_time}")
    logger.info(f"Configuration: process_all={process_all}, max_papers={max_papers or 'unlimited'}")
    
    try:
        # Check if another analysis is already running
        if paper_analysis_service.is_analyzing:
            logger.warning("Another analysis process is already running. Skipping this run.")
            return
        
        # 直接调用analyze_pending_papers并等待其完成，处理所有论文
        logger.info("Starting paper analysis and waiting for completion")
        result = await paper_analysis_service.analyze_pending_papers(
            process_all=process_all, 
            max_papers=max_papers
        )
        
        # Log the results
        status = result.get("status", "unknown")
        message = result.get("message", "No message provided")
        processed = result.get("processed", 0)
        failed = result.get("failed", 0)
        total = result.get("total_pending", 0)
        
        if status == "completed":
            logger.info(f"Analysis completed: {message} Total: {total}, Processed: {processed}, Failed: {failed}")
        elif status == "no_pending":
            logger.info(f"No papers to analyze: {message}")
        else:
            logger.warning(f"Analysis task status: {status}, Message: {message}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Analysis job completed in {duration:.2f} seconds.")
        
    except Exception as e:
        logger.error(f"Error in analysis job: {e}", exc_info=True)

async def main():
    """Main entry point."""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Analyze papers that have been fetched.')
    parser.add_argument('--limit', type=int, help='Maximum number of papers to analyze')
    parser.add_argument('--batch', action='store_true', help='Use batch mode instead of processing all papers')
    args = parser.parse_args()
    
    # 根据命令行参数设置配置
    process_all = not args.batch  # 默认处理所有论文，除非指定--batch
    max_papers = args.limit  # 可以是None或整数
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Log script start with a divider for readability in logs
    logger.info("=" * 80)
    logger.info("Starting paper analysis script")
    
    # Run the analysis job
    await analyze_papers(process_all=process_all, max_papers=max_papers)
    
    logger.info("Paper analysis script completed")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main()) 