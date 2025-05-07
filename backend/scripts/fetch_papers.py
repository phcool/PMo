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
    # Core machine learning and deep learning categories
    "cs.LG",   # Machine Learning
    "cs.AI",   # Artificial Intelligence
    "cs.CV",   # Computer Vision
    "cs.CL",   # Computational Linguistics/Natural Language Processing
    "cs.NE",   # Neural and Evolutionary Computing
    "stat.ML", # Statistical Machine Learning
    
    # Related application areas
    "cs.RO",   # Robotics
    "cs.IR",   # Information Retrieval
    "cs.MM",   # Multimedia
    "cs.SD",   # Sound
    "cs.HC",   # Human-Computer Interaction
    
    # Systems and algorithms
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

# Batch size: Number of papers to fetch from arXiv each time
BATCH_SIZE = int(os.getenv("FETCH_BATCH_SIZE", "100"))

# Total target count: Total number of papers to fetch
TOTAL_MAX_RESULTS = int(os.getenv("FETCH_TOTAL_MAX_RESULTS", "1000"))

# Delay between batches (seconds): Avoid frequent requests to arXiv API
BATCH_DELAY = int(os.getenv("FETCH_BATCH_DELAY", "3"))

async def fetch_papers_batch(categories, skip, max_results):
    """Fetch a batch of papers with a starting offset"""
    logger.info(f"Fetching papers {skip+1}-{skip+max_results}...")
    try:
        papers = await ArxivService.fetch_recent_papers(
            categories=categories,
            max_results=max_results,
            offset=skip
        )
        return papers
    except Exception as e:
        logger.error(f"Failed to fetch batch of papers (skip={skip}): {e}", exc_info=True)
        return []

async def fetch_papers():
    """Fetch papers from arXiv in batches and store them in the database and vector index"""
    start_time = datetime.now()
    logger.info(f"Starting paper fetch task, time: {start_time}, target count: {TOTAL_MAX_RESULTS}")
    
    total_fetched = 0
    total_added = 0
    all_added_ids = set()
    
    try:
        # Fetch in batches
        for batch_start in range(0, TOTAL_MAX_RESULTS, BATCH_SIZE):
            # Calculate current batch size
            current_batch_size = min(BATCH_SIZE, TOTAL_MAX_RESULTS - batch_start)
            
            # Fetch a batch of papers
            batch_papers = await fetch_papers_batch(
                categories=DEFAULT_CATEGORIES,
                skip=batch_start,
                max_results=current_batch_size
            )
            
            if not batch_papers:
                logger.info(f"Batch {batch_start//BATCH_SIZE + 1} did not return any papers, stopping fetch")
                break
                
            total_fetched += len(batch_papers)
            
            # Add to database
            added_ids = await db_service.add_papers(batch_papers)
            
            # If there are newly added papers, update the vector index
            if added_ids:
                papers_to_add = [p for p in batch_papers if p.paper_id in added_ids]
                await vector_search_service.add_papers(papers_to_add)
                
                all_added_ids.update(added_ids)
                total_added += len(added_ids)
                
                logger.info(f"Batch {batch_start//BATCH_SIZE + 1}: Fetched {len(batch_papers)} papers, added {len(added_ids)} new papers")
            else:
                logger.info(f"Batch {batch_start//BATCH_SIZE + 1}: Fetched {len(batch_papers)} papers, no new papers added")
            
            # Stop if we've fetched enough papers or if this batch returned fewer than requested
            if total_fetched >= TOTAL_MAX_RESULTS or len(batch_papers) < current_batch_size:
                break
                
            # Add delay between batches to avoid sending too many requests to arXiv API
            if batch_start + BATCH_SIZE < TOTAL_MAX_RESULTS:
                logger.info(f"Waiting {BATCH_DELAY} seconds before fetching the next batch...")
                await asyncio.sleep(BATCH_DELAY)
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Fetch task completed, took {duration:.2f} seconds. Total fetched: {total_fetched} papers, added {total_added} new papers.")
        
    except Exception as e:
        logger.error(f"Error occurred during fetch task: {e}", exc_info=True)

async def main():
    """Main entry point."""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Log script start with a divider for readability in logs
    logger.info("=" * 80)
    logger.info("Starting paper fetch script")
    logger.info(f"Configuration: Batch size={BATCH_SIZE}, Total target count={TOTAL_MAX_RESULTS}, Batch delay={BATCH_DELAY} seconds")
    
    # Run the fetch job
    await fetch_papers()
    
    logger.info("Paper fetch script completed")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main()) 