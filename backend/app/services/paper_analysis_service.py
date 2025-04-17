import logging
import asyncio
from typing import List, Optional, Dict, Any
import time
from datetime import datetime

from app.models.paper import Paper, PaperAnalysis
from app.services.db_service import db_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class PaperAnalysisService:
    """
    论文分析服务，负责协调PDF分析任务
    """
    
    def __init__(self):
        """初始化论文分析服务"""
        self.is_analyzing = False
        self.current_task = None
        self.batch_size = 5  # 每批处理的论文数
        
    async def analyze_paper(self, paper_id: str) -> Optional[PaperAnalysis]:
        """
        分析单篇论文
        
        Args:
            paper_id: 论文ID
            
        Returns:
            分析结果或None（如果分析失败）
        """
        try:
            # 获取论文详情
            paper = await db_service.get_paper_by_id(paper_id)
            if not paper:
                logger.error(f"论文不存在: {paper_id}")
                return None
            
            # 检查是否已有分析
            existing_analysis = await db_service.get_paper_analysis(paper_id)
            if existing_analysis:
                logger.info(f"论文已有分析结果: {paper_id}")
                return existing_analysis
            
            # 分析PDF
            analysis = await llm_service.analyze_pdf(paper_id, paper.pdf_url)
            if not analysis:
                logger.error(f"分析论文失败: {paper_id}")
                return None
            
            # 保存分析结果
            success = await db_service.save_paper_analysis(analysis)
            if not success:
                logger.error(f"保存分析结果失败: {paper_id}")
                return None
            
            return analysis
            
        except Exception as e:
            logger.error(f"分析论文时出错: {e}")
            return None
    
    async def analyze_pending_papers(self) -> Dict[str, Any]:
        """
        分析待处理的论文
        
        Returns:
            分析统计信息
        """
        if self.is_analyzing:
            return {
                "status": "in_progress",
                "message": "已有分析任务正在进行中"
            }
        
        try:
            self.is_analyzing = True
            start_time = time.time()
            
            # 获取未分析的论文
            papers = await db_service.get_papers_without_analysis(self.batch_size)
            if not papers:
                self.is_analyzing = False
                return {
                    "status": "completed",
                    "message": "没有待分析的论文",
                    "processed": 0,
                    "successful": 0,
                    "failed": 0,
                    "duration_seconds": time.time() - start_time
                }
            
            logger.info(f"开始分析 {len(papers)} 篇论文")
            
            # 处理每篇论文
            successful = 0
            failed = 0
            
            for paper in papers:
                try:
                    analysis = await llm_service.analyze_pdf(paper.paper_id, paper.pdf_url)
                    if analysis:
                        success = await db_service.save_paper_analysis(analysis)
                        if success:
                            successful += 1
                            logger.info(f"成功分析论文: {paper.paper_id}")
                        else:
                            failed += 1
                            logger.error(f"保存分析结果失败: {paper.paper_id}")
                    else:
                        failed += 1
                        logger.error(f"分析论文失败: {paper.paper_id}")
                except Exception as e:
                    failed += 1
                    logger.error(f"处理论文时出错: {paper.paper_id}, 错误: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                "status": "completed",
                "message": f"完成分析 {len(papers)} 篇论文",
                "processed": len(papers),
                "successful": successful,
                "failed": failed,
                "duration_seconds": duration
            }
            
            logger.info(f"分析任务完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"分析待处理论文时出错: {e}")
            return {
                "status": "error",
                "message": f"分析论文时出错: {str(e)}",
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "duration_seconds": time.time() - start_time
            }
        finally:
            self.is_analyzing = False
    
    async def start_analysis_task(self) -> Dict[str, Any]:
        """
        启动异步分析任务
        
        Returns:
            任务状态信息
        """
        if self.is_analyzing:
            return {
                "status": "in_progress",
                "message": "已有分析任务正在进行中"
            }
        
        # 创建异步任务
        self.current_task = asyncio.create_task(self.analyze_pending_papers())
        
        return {
            "status": "started",
            "message": "已启动论文分析任务",
            "timestamp": datetime.now().isoformat()
        }

# 创建全局实例
paper_analysis_service = PaperAnalysisService() 