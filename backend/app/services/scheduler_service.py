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

# Service singleton
db_service = DBService()
vector_search_service = VectorSearchService()

class SchedulerService:
    """
    Paper scheduling service, responsible for periodically fetching new papers in the background
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_run_time = None
        self.last_analysis_time = None
        
        # Extended default categories, including all computer science and deep learning related fields
        self.default_categories = [
            # Core machine learning and deep learning categories
            "cs.LG",   # Machine Learning
            "cs.AI",   # Artificial Intelligence
            "cs.CV",   # Computer Vision
            "cs.CL",   # Computational Linguistics/Natural Language Processing
            "cs.NE",   # Neural and Evolutionary Computing
            "stat.ML", # Statistical Machine Learning
            
            # Related application domains
            "cs.RO",   # Robotics
            "cs.IR",   # Information Retrieval
            "cs.MM",   # Multimedia
            "cs.SD",   # Sound
            "cs.HC",   # Human-Computer Interaction
            
            # Systems and Algorithms
            "cs.DC",   # Distributed Computing
            "cs.DS",   # Data Structures and Algorithms
            "cs.DB",   # Databases
            "cs.PL",   # Programming Languages
            "cs.NA",   # Numerical Analysis
            "cs.AR",   # Hardware Architecture
            
            # Other related fields
            "cs.GT",   # Game Theory
            "cs.CC",   # Computational Complexity
            "cs.NI",   # Networking and Internet Architecture
            "cs.CR",   # Cryptography and Security
            "cs.SE"    # Software Engineering
        ]
        
        self.default_max_results = 100  # Increased default fetch count
        
        # Get configuration from environment variables
        self.cron_schedule = os.getenv("PAPER_FETCH_SCHEDULE", "0 */8 * * *")  # Default every 8 hours
        self.analysis_schedule = os.getenv("PAPER_ANALYSIS_SCHEDULE", "30 */8 * * *")  # Default every 8 hours, but 30 minutes after fetching
        
    async def fetch_papers_task(self):
        """Scheduled task for fetching papers"""
        try:
            logger.info("Starting scheduled paper fetch task")
            self.last_run_time = datetime.now()
            
            # Fetch papers from arXiv
            papers = await ArxivService.fetch_recent_papers(
                categories=self.default_categories,
                max_results=self.default_max_results
            )
            
            if not papers:
                logger.info("No new papers found")
                return
                
            # Add to database
            added_ids = await db_service.add_papers(papers)
            
            # Add to vector search index
            if added_ids:
                papers_to_add = [p for p in papers if p.paper_id in added_ids]
                await vector_search_service.add_papers(papers_to_add)
                
            logger.info(f"Scheduled task fetched {len(papers)} papers, added {len(added_ids)} new papers")
            
            # Note: No longer automatically starting analysis task here
            # Analysis task is handled by a separate scheduled job
        
        except Exception as e:
            logger.error(f"Scheduled paper fetch task failed: {e}")
    
    async def analyze_papers_task(self):
        """Scheduled task for analyzing papers"""
        try:
            logger.info("Starting scheduled paper analysis task")
            self.last_analysis_time = datetime.now()
            
            # Skip if already analyzing
            if paper_analysis_service.is_analyzing:
                logger.info("Analysis task is already in progress, skipping this execution")
                return
                
            # Start new analysis task
            analysis_result = await paper_analysis_service.start_analysis_task()
            logger.info(f"Started paper analysis task: {analysis_result}")
            
        except Exception as e:
            logger.error(f"Scheduled paper analysis task failed: {e}")
    
    def start(self):
        """Start scheduled tasks"""
        if self.is_running:
            logger.warning("Scheduled tasks are already running")
            return
            
        # Add paper fetch scheduled task
        self.scheduler.add_job(
            self.fetch_papers_task,
            CronTrigger.from_crontab(self.cron_schedule),
            id="fetch_papers_job",
            replace_existing=True
        )
        
        # Add paper analysis scheduled task
        self.scheduler.add_job(
            self.analyze_papers_task,
            CronTrigger.from_crontab(self.analysis_schedule),
            id="analyze_papers_job",
            replace_existing=True
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"Paper scheduling service started, fetch schedule: {self.cron_schedule}, analysis schedule: {self.analysis_schedule}")
    
    def stop(self):
        """Stop scheduled tasks"""
        if not self.is_running:
            return
            
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Paper scheduling service stopped")
    
    async def manual_fetch(self, categories: Optional[List[str]] = None, max_results: int = 50) -> dict:
        """
        Manually trigger paper fetching
        
        Args:
            categories: List of paper categories to fetch
            max_results: Maximum number of papers to fetch
            
        Returns:
            Dictionary containing the fetch results
        """
        if categories is None:
            categories = self.default_categories
            
        try:
            # Fetch papers
            papers = await ArxivService.fetch_recent_papers(
                categories=categories,
                max_results=max_results
            )
            
            if not papers:
                return {"status": "success", "message": "No new papers found", "count": 0}
                
            # Add to database
            added_ids = await db_service.add_papers(papers)
            
            # Add to vector search index
            if added_ids:
                papers_to_add = [p for p in papers if p.paper_id in added_ids]
                await vector_search_service.add_papers(papers_to_add)
                
            result = {
                "status": "success",
                "message": f"Fetched {len(papers)} papers, added {len(added_ids)} new papers",
                "count": len(added_ids),
                "timestamp": datetime.now().isoformat()
            }
            
            # Note: No longer automatically starting analysis task here
            # Analysis task is handled by a separate scheduled job or manual trigger
            
            return result
            
        except Exception as e:
            logger.error(f"Manual paper fetch failed: {e}")
            return {
                "status": "error",
                "message": f"Paper fetch failed: {str(e)}",
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
    
    async def manual_analyze(self) -> dict:
        """
        Manually trigger paper analysis
        
        Returns:
            Dictionary containing the analysis results
        """
        try:
            if paper_analysis_service.is_analyzing:
                return {
                    "status": "in_progress",
                    "message": "An analysis task is already in progress"
                }
                
            # Start analysis task
            result = await paper_analysis_service.start_analysis_task()
            return result
            
        except Exception as e:
            logger.error(f"Manual paper analysis start failed: {e}")
            return {
                "status": "error",
                "message": f"Failed to start paper analysis: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    @property
    def status(self) -> dict:
        """Get scheduled task status"""
        return {
            "is_running": self.is_running,
            "last_fetch_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_analysis_time": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "fetch_schedule": self.cron_schedule,
            "analysis_schedule": self.analysis_schedule,
            "default_categories": self.default_categories
        }

# Create global singleton
scheduler_service = SchedulerService() 