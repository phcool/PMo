import os
import sys
import asyncio
import logging
from datetime import datetime, date, timedelta

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fetch_papers")

# Import our services
from app.services.arxiv_service import arxiv_service
from app.services.db_service import db_service
from app.services.vector_search_service import vector_search_service

# Configuration
BATCH_DAYS = 1
DEFAULT_DAYS = 1
BATCH_DELAY = 3
MAX_RESULTS_PER_BATCH = 10000


async def fetch_papers_batch(start_date, end_date):
    """Fetch a batch of papers for a specific date range"""
    logger.info(f"Fetching papers from {start_date} to {end_date}...")
    try:
        papers = await arxiv_service.fetch_papers(
            start_date=start_date,
            end_date=end_date,
            max_results=MAX_RESULTS_PER_BATCH
        )
        return papers
    except Exception as e:
        logger.error(f"Failed to fetch batch (dates: {start_date} to {end_date}): {e}", exc_info=True)
        return []


async def fetch_papers(days=None):
    if days is None:
        days = DEFAULT_DAYS
        
    start_time = datetime.now()
    today = date.today()
    earliest_date = today - timedelta(days=days)
    
    logger.info(f"Starting paper fetch task, time: {start_time}")
    logger.info(f"Fetching papers from {earliest_date} to {today} ({days} days total)")
    logger.info(f"Using {BATCH_DAYS}-day batches with max {MAX_RESULTS_PER_BATCH} results per batch")
    
    total_fetched = 0
    total_added_db = 0
    batch_num = 1
    
    try:
        # Calculate date ranges for each batch (working backwards from today)
        current_end_date = today
        
        while current_end_date > earliest_date:
            # Calculate start date for this batch
            current_start_date = max(current_end_date - timedelta(days=BATCH_DAYS - 1), earliest_date)
            
            # Fetch papers for this date range
            batch_papers = await fetch_papers_batch(
                start_date=current_start_date,
                end_date=current_end_date,
            )
            
            if not batch_papers:
                logger.info(f"Batch did not return any papers, continuing to next batch.")

                
            total_fetched += len(batch_papers)
                
            # Add papers to database
            added_db_ids = await db_service.add_papers(batch_papers)
            
            if not added_db_ids:
                logger.info(f"No new papers in batch {batch_num} added to DB. All papers already exist.")
        
            await vector_search_service.add_papers(batch_papers)
            total_added_db += len(added_db_ids)
            logger.info(f"Batch {batch_num}: Fetched {len(batch_papers)} papers, added {len(added_db_ids)} new papers to DB and vector search.")
            
            # Move to the next batch (earlier dates)
            current_end_date = current_start_date - timedelta(days=1)
            batch_num += 1
            
            # Wait between batches to avoid overwhelming arXiv API
            if current_end_date > earliest_date:
                logger.info(f"Waiting {BATCH_DELAY} seconds before fetching the next batch...")
                await asyncio.sleep(BATCH_DELAY)
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Fetch task completed in {duration:.2f} seconds. Total fetched: {total_fetched} papers, added to DB: {total_added_db} new papers.")
        
    except Exception as e:
        logger.error(f"Error occurred during fetch_papers task: {e}", exc_info=True)


async def main():
    
    import argparse
    parser = argparse.ArgumentParser(description='Fetch papers from arXiv')
    parser.add_argument('--days', type=int, default=None)
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("Starting paper fetch script")
    logger.info(f"Configuration: Batch days={BATCH_DAYS}, Default days={DEFAULT_DAYS}, Batch delay={BATCH_DELAY} seconds")
    logger.info(f"Max results per batch: {MAX_RESULTS_PER_BATCH}")

    await fetch_papers(days=args.days)
    
    logger.info("Paper fetch script completed")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main()) 