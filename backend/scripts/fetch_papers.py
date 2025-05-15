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
import aiohttp  # For async HTTP requests
import oss2     # For Alibaba Cloud OSS

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

# OSS Configuration
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME")

async def download_and_upload_pdf(http_session, paper_obj, oss_bucket_client):
    """Downloads a PDF from paper_obj.pdf_url and uploads it to OSS."""
    if not paper_obj.pdf_url:
        logger.warning(f"No PDF URL for paper {paper_obj.paper_id}. Skipping download.")
        return False

    pdf_url = paper_obj.pdf_url
    # Ensure the URL is a direct PDF link, common for arxiv.Result.pdf_url
    # If it were an abstract link, it might need transformation:
    # if "arxiv.org/abs/" in pdf_url:
    #     pdf_url = pdf_url.replace("/abs/", "/pdf/") + ".pdf"
    # elif not pdf_url.lower().endswith('.pdf'):
    #     pdf_url += ".pdf" # Heuristic if it's like /pdf/{id}

    # Sanitize paper_id for use in path (though arXiv IDs are usually safe)
    sanitized_paper_id = paper_obj.paper_id.replace('/', '_').replace(':', '_')
    object_key = f"papers/{sanitized_paper_id}/{sanitized_paper_id}.pdf"
    
    logger.info(f"Attempting to download PDF for {paper_obj.paper_id} from {pdf_url}")

    try:
        async with http_session.get(pdf_url) as response:
            if response.status != 200:
                logger.error(f"Failed to download PDF for {paper_obj.paper_id}. Status: {response.status}. URL: {pdf_url}")
                return False
            pdf_content = await response.read()
            logger.info(f"Successfully downloaded PDF for {paper_obj.paper_id} ({len(pdf_content)} bytes)")

        if oss_bucket_client:
            try:
                oss_bucket_client.put_object(object_key, pdf_content)
                # Construct the full OSS URL for logging or potential future storage
                oss_pdf_url = f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{object_key}" # Note: Endpoint might not always prefix bucket for URL
                logger.info(f"Successfully uploaded PDF for {paper_obj.paper_id} to OSS: {oss_pdf_url}")
                # Optionally, update the paper object or database with the OSS path/URL here
                # e.g., await db_service.update_paper_oss_url(paper_obj.paper_id, oss_pdf_url)
                return True
            except oss2.exceptions.OssError as e:
                logger.error(f"Failed to upload PDF for {paper_obj.paper_id} to OSS. Object key: {object_key}. Error: {e}")
                return False
        else:
            logger.warning(f"OSS bucket not configured for paper {paper_obj.paper_id}. PDF downloaded but not uploaded.")
            return False # Or True if local download is sufficient without OSS

    except aiohttp.ClientError as e:
        logger.error(f"aiohttp.ClientError downloading PDF for {paper_obj.paper_id} from {pdf_url}. Error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during PDF processing for {paper_obj.paper_id}. Error: {e}", exc_info=True)
        return False

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

async def fetch_papers(http_session, oss_bucket_client):
    """Fetch papers from arXiv in batches, store them, and upload PDFs to OSS."""
    start_time = datetime.now()
    logger.info(f"Starting paper fetch task, time: {start_time}, target count: {TOTAL_MAX_RESULTS}")
    
    total_fetched = 0
    total_added_db = 0 # Renamed to distinguish from PDF uploads
    total_pdf_uploaded = 0
    all_added_ids = set()
    
    try:
        for batch_start in range(0, TOTAL_MAX_RESULTS, BATCH_SIZE):
            current_batch_size = min(BATCH_SIZE, TOTAL_MAX_RESULTS - batch_start)
            
            batch_papers = await fetch_papers_batch(
                categories=DEFAULT_CATEGORIES,
                skip=batch_start,
                max_results=current_batch_size
            )
            
            if not batch_papers:
                logger.info(f"Batch {batch_start//BATCH_SIZE + 1} did not return any papers, stopping fetch.")
                break
                
            total_fetched += len(batch_papers)
            
            added_db_ids = await db_service.add_papers(batch_papers)
            
            if not added_db_ids:
                logger.info(f"No new papers in batch {batch_start//BATCH_SIZE + 1} added to DB. Assuming all exist. Stopping fetch.")
                break
            
            papers_to_process_further = [p for p in batch_papers if p.paper_id in added_db_ids]
            
            # If only a subset was added, and the first paper of the batch wasn't one of them,
            # it implies we've caught up to existing papers.
            if len(added_db_ids) < len(batch_papers) and batch_papers[0].paper_id not in added_db_ids:
                logger.info(f"First paper of batch {batch_start//BATCH_SIZE + 1} already existed. Processing {len(added_db_ids)} newly added ones from this batch and stopping.")
                if papers_to_process_further:
                    await vector_search_service.add_papers(papers_to_process_further)
                    all_added_ids.update(added_db_ids)
                    total_added_db += len(added_db_ids)
                    # PDF Upload for these papers before breaking
                    if oss_bucket_client and http_session:
                        logger.info(f"Starting PDF download/upload for {len(papers_to_process_further)} papers from final partial batch.")
                        for paper_obj in papers_to_process_further:
                            if await download_and_upload_pdf(http_session, paper_obj, oss_bucket_client):
                                total_pdf_uploaded += 1
                break 
            
            if papers_to_process_further:
                await vector_search_service.add_papers(papers_to_process_further)
                all_added_ids.update(added_db_ids)
                total_added_db += len(added_db_ids)
                logger.info(f"Batch {batch_start//BATCH_SIZE + 1}: Fetched {len(batch_papers)} papers, added {len(added_db_ids)} new papers to DB.")

                # PDF Download and Upload
                if oss_bucket_client and http_session:
                    logger.info(f"Starting PDF download/upload for {len(papers_to_process_further)} newly added papers.")
                    batch_pdf_uploads = 0
                    for paper_obj in papers_to_process_further:
                        if await download_and_upload_pdf(http_session, paper_obj, oss_bucket_client):
                            batch_pdf_uploads += 1
                    total_pdf_uploaded += batch_pdf_uploads
                    logger.info(f"Batch {batch_start//BATCH_SIZE + 1}: Successfully uploaded {batch_pdf_uploads} PDFs to OSS.")
            else:
                logger.info(f"Batch {batch_start//BATCH_SIZE + 1}: Fetched {len(batch_papers)} papers, no new papers added to DB in this iteration (unexpected, check logic if added_db_ids was non-empty).")

            if total_fetched >= TOTAL_MAX_RESULTS or len(batch_papers) < current_batch_size:
                logger.info("Reached target fetch count or end of available new papers.")
                break
                
            if batch_start + BATCH_SIZE < TOTAL_MAX_RESULTS:
                logger.info(f"Waiting {BATCH_DELAY} seconds before fetching the next batch...")
                await asyncio.sleep(BATCH_DELAY)
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Fetch task completed, took {duration:.2f} seconds. Total fetched from arXiv: {total_fetched} papers, added to DB: {total_added_db} new papers. PDFs uploaded to OSS: {total_pdf_uploaded}.")
        
    except Exception as e:
        logger.error(f"Error occurred during fetch_papers task: {e}", exc_info=True)

async def main():
    """Main entry point."""
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("Starting paper fetch script")
    logger.info(f"Configuration: Batch size={BATCH_SIZE}, Total target count={TOTAL_MAX_RESULTS}, Batch delay={BATCH_DELAY} seconds")

    oss_auth = None
    oss_bucket_client = None
    if OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET and OSS_ENDPOINT and OSS_BUCKET_NAME:
        try:
            oss_auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
            # Use a timeout for OSS operations if desired, e.g., oss2.Bucket(oss_auth, OSS_ENDPOINT, OSS_BUCKET_NAME, connect_timeout=30)
            oss_bucket_client = oss2.Bucket(oss_auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
            # Test connection by listing a prefix or getting bucket info (optional)
            # Example: oss_bucket_client.list_objects(prefix='test_connection_prefix/', max_keys=1)
            logger.info(f"OSS client initialized for bucket: {OSS_BUCKET_NAME} at endpoint: {OSS_ENDPOINT}")
        except Exception as e:
            logger.error(f"Failed to initialize OSS client: {e}", exc_info=True)
            oss_bucket_client = None # Ensure it's None if initialization fails
    else:
        logger.warning("OSS configuration variables are not fully set. PDF upload to OSS will be disabled.")

    # Create a single aiohttp session to be reused for all downloads
    async with aiohttp.ClientSession() as http_client_session:
        logger.info("aiohttp.ClientSession created.")
        await fetch_papers(http_client_session, oss_bucket_client)
    
    logger.info("Paper fetch script completed")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main()) 