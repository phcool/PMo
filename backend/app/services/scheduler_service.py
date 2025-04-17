import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.arxiv_service import ArxivService
from app.services.db_service import DBService
from app.services.vector_search_service import VectorSearchService
from app.services.paper_analysis_service import paper_analysis_service

logger = logging.getLogger(__name__)

# 服务单例
db_service = DBService()
vector_search_service = VectorSearchService()

class SchedulerService:
    """
    论文定时获取服务，负责后台周期性获取新论文
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_run_time = None
        
        # 扩展默认类别，包含所有计算机科学和深度学习相关方向
        self.default_categories = [
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
        
        self.default_max_results = 100  # 增加默认获取数量
        
        # 从环境变量获取配置
        self.cron_schedule = os.getenv("PAPER_FETCH_SCHEDULE", "0 */8 * * *")  # 默认每8小时
        
    async def fetch_papers_task(self):
        """定时获取论文的任务"""
        try:
            logger.info("开始定时获取论文任务")
            self.last_run_time = datetime.now()
            
            # 从arXiv获取论文
            papers = await ArxivService.fetch_recent_papers(
                categories=self.default_categories,
                max_results=self.default_max_results
            )
            
            if not papers:
                logger.info("没有找到新论文")
                return
                
            # 添加到数据库
            added_ids = await db_service.add_papers(papers)
            
            # 添加到向量搜索索引
            if added_ids:
                papers_to_add = [p for p in papers if p.paper_id in added_ids]
                await vector_search_service.add_papers(papers_to_add)
                
            logger.info(f"定时任务获取了 {len(papers)} 篇论文，添加了 {len(added_ids)} 篇新论文")
            
            # 如果有新论文，启动分析任务
            if added_ids:
                # 等待5秒，确保数据库操作完成
                await asyncio.sleep(5)
                try:
                    analysis_result = await paper_analysis_service.start_analysis_task()
                    logger.info(f"启动论文分析任务: {analysis_result}")
                except Exception as e:
                    logger.error(f"启动论文分析任务失败: {e}")
        
        except Exception as e:
            logger.error(f"定时获取论文任务失败: {e}")
    
    def start(self):
        """启动定时任务"""
        if self.is_running:
            logger.warning("定时任务已经在运行中")
            return
            
        # 添加定时任务，使用cron表达式
        self.scheduler.add_job(
            self.fetch_papers_task,
            CronTrigger.from_crontab(self.cron_schedule),
            id="fetch_papers_job",
            replace_existing=True
        )
        
        # # 添加一个立即执行一次的任务
        # self.scheduler.add_job(
        #     self.fetch_papers_task,
        #     'date',
        #     run_date=datetime.now(),
        #     id="fetch_papers_initial_job"
        # )
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"论文定时获取服务已启动，调度计划: {self.cron_schedule}")
    
    def stop(self):
        """停止定时任务"""
        if not self.is_running:
            return
            
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("论文定时获取服务已停止")
    
    async def manual_fetch(self, categories: Optional[List[str]] = None, max_results: int = 50) -> dict:
        """
        手动触发获取论文
        
        Args:
            categories: 要获取的论文类别列表
            max_results: 最大获取数量
            
        Returns:
            包含获取结果的字典
        """
        if categories is None:
            categories = self.default_categories
            
        try:
            # 获取论文
            papers = await ArxivService.fetch_recent_papers(
                categories=categories,
                max_results=max_results
            )
            
            if not papers:
                return {"status": "success", "message": "没有找到新论文", "count": 0}
                
            # 添加到数据库
            added_ids = await db_service.add_papers(papers)
            
            # 添加到向量搜索索引
            if added_ids:
                papers_to_add = [p for p in papers if p.paper_id in added_ids]
                await vector_search_service.add_papers(papers_to_add)
                
            result = {
                "status": "success",
                "message": f"获取了 {len(papers)} 篇论文，添加了 {len(added_ids)} 篇新论文",
                "count": len(added_ids),
                "timestamp": datetime.now().isoformat()
            }
            
            # 如果有新论文，启动分析任务
            if added_ids:
                # 等待5秒，确保数据库操作完成
                await asyncio.sleep(5)
                try:
                    analysis_result = await paper_analysis_service.start_analysis_task()
                    result["analysis_task"] = analysis_result
                except Exception as e:
                    logger.error(f"启动论文分析任务失败: {e}")
                    result["analysis_task"] = {"status": "error", "message": f"启动分析任务失败: {str(e)}"}
            
            return result
            
        except Exception as e:
            logger.error(f"手动获取论文失败: {e}")
            return {
                "status": "error",
                "message": f"获取论文失败: {str(e)}",
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
    
    @property
    def status(self) -> dict:
        """获取定时任务状态"""
        return {
            "is_running": self.is_running,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "schedule": self.cron_schedule,
            "default_categories": self.default_categories
        }

# 创建全局单例
scheduler_service = SchedulerService() 