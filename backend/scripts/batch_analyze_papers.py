#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
import logging

# 确保可以导入app模块
sys.path.append(str(Path(__file__).parent.parent))

# 加载环境变量
from dotenv import load_dotenv
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

from app.services.db_service import db_service
from app.services.paper_analysis_service import paper_analysis_service

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "batch_analysis.log")
    ]
)
logger = logging.getLogger("batch_analyzer")

async def analyze_all_papers(batch_size=5, max_papers=None, delay_between_papers=2):
    """
    分析数据库中所有未分析的论文
    
    Args:
        batch_size: 每次查询的论文数量
        max_papers: 最大处理论文数量，None表示处理所有
        delay_between_papers: 每篇论文分析之间的延迟（秒）
    """
    start_time = time.time()
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    # 获取未分析论文总数
    total_papers = await count_papers_without_analysis()
    if max_papers:
        papers_to_process = min(total_papers, max_papers)
    else:
        papers_to_process = total_papers
    
    logger.info(f"开始批量分析，共 {papers_to_process} 篇论文待分析")
    print(f"\n{'='*50}")
    print(f"开始批量分析论文 - 共 {papers_to_process} 篇待处理")
    print(f"{'='*50}")
    
    # 持续获取和处理论文，直到所有论文都已处理或达到最大数量
    while total_processed < papers_to_process:
        # 获取一批未分析的论文
        papers = await db_service.get_papers_without_analysis(limit=batch_size)
        if not papers:
            logger.info("没有更多未分析的论文")
            break
        
        # 处理这一批论文
        for i, paper in enumerate(papers):
            if total_processed >= papers_to_process:
                break
                
            # 更新进度信息
            total_processed += 1
            progress = (total_processed / papers_to_process) * 100
            
            print(f"\n[{total_processed}/{papers_to_process}] ({progress:.1f}%) 开始分析: {paper.title}")
            print(f"论文ID: {paper.paper_id}")
            print(f"作者: {', '.join(paper.authors[:3])}{' 等' if len(paper.authors) > 3 else ''}")
            
            start_paper_time = time.time()
            
            try:
                # 分析论文
                logger.info(f"开始分析论文: {paper.paper_id} - {paper.title}")
                # 直接使用paper_analysis_service分析论文
                analysis = await paper_analysis_service.analyze_paper(paper.paper_id)
                
                if analysis:
                    total_success += 1
                    duration = time.time() - start_paper_time
                    logger.info(f"成功分析论文 [{total_processed}/{papers_to_process}]: {paper.paper_id}, 耗时: {duration:.1f}秒")
                    print(f"✅ 分析成功! 耗时: {duration:.1f}秒")
                    
                    # 显示分析结果摘要
                    summary = analysis.summary[:150] + "..." if analysis.summary and len(analysis.summary) > 150 else analysis.summary
                    print(f"摘要: {summary}")
                else:
                    total_failed += 1
                    logger.error(f"分析论文失败 [{total_processed}/{papers_to_process}]: {paper.paper_id}")
                    print(f"❌ 分析失败!")
            
            except Exception as e:
                total_failed += 1
                logger.exception(f"处理论文时出错 [{total_processed}/{papers_to_process}]: {paper.paper_id}, 错误: {str(e)}")
                print(f"❌ 分析错误: {str(e)}")
            
            # 打印当前进度统计
            elapsed = time.time() - start_time
            papers_per_hour = (total_processed / elapsed) * 3600 if elapsed > 0 else 0
            remaining = (papers_to_process - total_processed) / papers_per_hour * 3600 if papers_per_hour > 0 else 0
            
            print(f"\n当前进度: {progress:.1f}% ({total_processed}/{papers_to_process})")
            print(f"成功: {total_success}, 失败: {total_failed}")
            print(f"处理速度: {papers_per_hour:.1f} 篇/小时")
            
            hours, remainder = divmod(remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"预计剩余时间: {int(hours)}小时 {int(minutes)}分钟 {int(seconds)}秒")
            
            # 每篇论文之间添加延迟，避免API请求过于频繁
            if total_processed < papers_to_process and i < len(papers) - 1:
                await asyncio.sleep(delay_between_papers)
    
    # 完成处理
    total_time = time.time() - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    print(f"\n{'='*50}")
    print(f"批量分析完成!")
    print(f"总耗时: {int(hours)}小时 {int(minutes)}分钟 {int(seconds)}秒")
    print(f"处理论文: {total_processed}篇")
    print(f"分析成功: {total_success}篇")
    print(f"分析失败: {total_failed}篇")
    print(f"成功率: {(total_success/total_processed*100):.1f}%" if total_processed > 0 else "N/A")
    print(f"{'='*50}")
    
    logger.info(f"批量分析完成! 总计: {total_processed}, 成功: {total_success}, 失败: {total_failed}, 耗时: {total_time:.1f}秒")
    return {
        "total_processed": total_processed,
        "total_success": total_success,
        "total_failed": total_failed,
        "elapsed_seconds": total_time
    }

async def count_papers_without_analysis():
    """计算需要分析的论文数量"""
    try:
        # 这里我们取一个大的数值来估计总数
        papers = await db_service.get_papers_without_analysis(limit=10000)
        return len(papers)
    except Exception as e:
        logger.error(f"获取未分析论文数量时出错: {e}")
        return 0

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量分析论文PDF')
    parser.add_argument('--batch-size', type=int, default=5, help='每批处理的论文数量')
    parser.add_argument('--max-papers', type=int, default=None, help='最大处理论文数量，不指定则处理所有')
    parser.add_argument('--delay', type=float, default=2.0, help='每篇论文之间的延迟(秒)')
    parser.add_argument('--scheduler', action='store_true', help='使用scheduler服务的start_analysis_task启动分析，不逐个处理')
    args = parser.parse_args()
    
    print(f"开始论文批量分析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.scheduler:
        from app.services.scheduler_service import scheduler_service
        print("使用调度器服务启动分析任务...")
        result = await scheduler_service.manual_analyze()
        print(f"分析任务启动结果: {result}")
    else:
        print(f"批次大小: {args.batch_size}")
        print(f"最大论文数: {'无限制' if args.max_papers is None else args.max_papers}")
        print(f"论文间延迟: {args.delay}秒")
        
        await analyze_all_papers(
            batch_size=args.batch_size,
            max_papers=args.max_papers,
            delay_between_papers=args.delay
        )

if __name__ == "__main__":
    # 设置事件循环策略，使用uvloop如果可用
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("使用 uvloop 加速")
    except ImportError:
        print("uvloop 不可用，使用标准事件循环")
    
    asyncio.run(main()) 