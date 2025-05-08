import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
import time
import os
import json
import re
import aiohttp
import fitz  # PyMuPDF
from datetime import datetime

from app.models.paper import Paper, PaperAnalysis
from app.services.db_service import db_service
from app.services.llm_service import llm_service
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)

def clean_latex_formula(formula: str) -> str:
    """
    Clean LaTeX math formulas, attempting to convert them to readable plain text
    
    Args:
        formula: LaTeX formula string
    
    Returns:
        Cleaned readable text
    """
    # Remove whitespace from beginning and end
    formula = formula.strip()
    
    # Replace common LaTeX commands
    replacements = {
        # Font and format commands
        r'\\bf{([^}]+)}': r'\1',
        r'\\mathbf{([^}]+)}': r'\1',
        r'\\it{([^}]+)}': r'\1',
        r'\\mathit{([^}]+)}': r'\1',
        r'\\text{([^}]+)}': r'\1',
        r'\\textbf{([^}]+)}': r'\1',
        r'\\textit{([^}]+)}': r'\1',
        r'\\rm{([^}]+)}': r'\1',
        r'\\mathrm{([^}]+)}': r'\1',
        r'\\emph{([^}]+)}': r'\1',
        
        # Spaces and separators
        r'\\space': ' ',
        r'\\,': ' ',
        r'\\;': ' ',
        r'\\quad': '  ',
        r'\\qquad': '    ',
        
        # Common mathematical symbols
        r'\\times': 'x',
        r'\\div': '/',
        r'\\pm': '+/-',
        r'\\cdot': '·',
        r'\\leq': '<=',
        r'\\geq': '>=',
        r'\\neq': '!=',
        r'\\approx': '~',
        r'\\equiv': '=',
        r'\\ldots': '...',
        r'\\rightarrow': '->',
        r'\\leftarrow': '<-',
        r'\\Rightarrow': '=>',
        r'\\Leftarrow': '<=',
        
        # Superscripts and subscripts
        r'\^{([^}]+)}': r'^(\1)',
        r'\_([a-zA-Z0-9])': r'_\1',
        r'\_\{([^}]+)\}': r'_(\1)',
        
        # Fractions
        r'\\frac{([^}]+)}{([^}]+)}': r'(\1)/(\2)',
        
        # Brackets
        r'\\left\(': '(',
        r'\\right\)': ')',
        r'\\left\[': '[',
        r'\\right\]': ']',
        r'\\left\\{': '{',
        r'\\right\\}': '}',
        
        # Greek letters (common)
        r'\\alpha': 'alpha',
        r'\\beta': 'beta',
        r'\\gamma': 'gamma',
        r'\\delta': 'delta',
        r'\\epsilon': 'epsilon',
        r'\\theta': 'theta',
        r'\\lambda': 'lambda',
        r'\\pi': 'pi',
        r'\\sigma': 'sigma',
        r'\\omega': 'omega',
    }
    
    # Apply all replacements
    for pattern, replacement in replacements.items():
        formula = re.sub(pattern, replacement, formula)
    
    # Remove any remaining LaTeX commands
    formula = re.sub(r'\\[a-zA-Z]+', '', formula)
    
    # Remove excess spaces
    formula = re.sub(r'\s+', ' ', formula).strip()
    
    return formula

def clean_text_for_api(text: str) -> str:
    """
    Clean text to make it API-friendly:
    1. Remove invalid Unicode characters and surrogate pairs
    2. Replace uncommon Unicode characters with basic ASCII alternatives
    3. Handle other potential encoding issues
    4. Ensure line breaks display correctly
    5. Process LaTeX mathematical symbols
    
    Args:
        text: Original text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
        
    # Remove null bytes (0x00), which cause PostgreSQL UTF-8 encoding errors
    text = text.replace('\x00', '')
        
    # Remove surrogate pairs and invalid Unicode characters
    # \ud800-\udfff is the Unicode surrogate pair range
    text = re.sub(r'[\ud800-\udfff]', '', text)
    
    # Process LaTeX math formulas
    # Handle specific patterns
    text = re.sub(r'\$\\bf\{(\d+)\s*\\space\s*([^}]+)\}\$', r'\1 \2', text)  # Like $\bf{3 \space billion}$
    
    # Simple math formulas (single-line $...$)
    text = re.sub(r'\$\\bf\{([^}]+)\}\$', r'\1', text)  # Replace bold command \bf{...}
    text = re.sub(r'\$\\mathbf\{([^}]+)\}\$', r'\1', text)  # Replace bold command \mathbf{...}
    text = re.sub(r'\$\\it\{([^}]+)\}\$', r'\1', text)  # Replace italic command \it{...}
    text = re.sub(r'\$\\mathit\{([^}]+)\}\$', r'\1', text)  # Replace italic command \mathit{...}
    text = re.sub(r'\$\\space\$', ' ', text)  # Replace space command \space
    text = re.sub(r'\$\\([a-zA-Z]+)\$', r'\1', text)  # Replace other simple commands \command
    
    # Handle more complex math formulas
    text = re.sub(r'\$([^$]+)\$', lambda m: clean_latex_formula(m.group(1)), text)  # Process content in $...$
    # Handle math environments with double dollar signs
    text = re.sub(r'\$\$([^$]+)\$\$', lambda m: clean_latex_formula(m.group(1)), text)  # Process content in $$...$$
    
    # Replace common math symbols and special characters
    replacements = {
        # Various quotes
        '"': '"', '"': '"', ''': "'", ''': "'",
        # Dashes and other punctuation
        '—': '-', '–': '-', '…': '...',
        # Common math symbols (may appear in papers)
        '×': 'x', '÷': '/', '≤': '<=', '≥': '>=', '≠': '!=', '≈': '~=',
        # Currency symbols
        '€': 'EUR', '£': 'GBP', '¥': 'JPY',
        # Superscripts, subscripts and other special characters
        '²': '^2', '³': '^3', '±': '+/-',
        # Other characters that may cause problems
        '\u2028': ' ', '\u2029': ' ',  # Line separator and paragraph separator
        # Handle potential HTML markup characters
        '<': '&lt;',
        '>': '&gt;'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Normalize line breaks (ensure all line breaks are \n)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # As a last measure, encode and then decode to remove any remaining problem characters
    # Use errors='ignore' to ignore characters that cannot be encoded
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    return text

# --- Helper function: for parsing and cleaning JSON returned by LLM --- 
def _parse_and_clean_llm_response(json_string: str, paper_id: str) -> Optional[Dict[str, Any]]:
    """Parse JSON string returned by LLM and perform data cleaning"""
    try:
        analysis_data = json.loads(json_string)
        
        # Data cleaning: ensure all fields are strings, and convert lists/dicts to appropriate string formats
        def clean_value(value):
            if isinstance(value, list):
                clean_list = []
                for item in value:
                    if isinstance(item, str):
                        item = item.strip()
                        # Try to add bullet points if not already present
                        if item and not re.match(r'^[-*•\d+\.\)]\s*', item):
                             item = "• " + item
                    clean_list.append(str(item))
                return '\n'.join(clean_list)
            elif isinstance(value, dict):
                # Handle nested dictionaries
                clean_dict = {}
                for k, v in value.items():
                    clean_dict[k] = clean_value(v)
                return str(clean_dict)
            elif value is None:
                return ""
            else:
                return str(value).strip()
        
        # Clean values of all fields
        for key in analysis_data:
            analysis_data[key] = clean_value(analysis_data[key])
        
        return analysis_data
            
    except json.JSONDecodeError as e:
        logger.error(f"[{paper_id}] JSON parsing error: {e}")
        logger.debug(f"[{paper_id}] Original string: {json_string}")
        return None
    except Exception as e:
        logger.error(f"[{paper_id}] Error cleaning analysis results: {e}")
        return None

"""
Paper Analysis Service, responsible for coordinating PDF extraction, LLM calls, and result storage
"""
class PaperAnalysisService:
    def __init__(self):
        """Initialize the paper analysis service"""
        self.is_analyzing = False
        self.current_task = None
        self.batch_size = int(os.getenv("ANALYSIS_BATCH_SIZE", "5")) # Get batch size from environment variable
        # Max chars for LLM input (adjust per model, e.g., qwen-turbo 8k context -> ~24k chars)
        self.max_llm_input_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "50000"))
    
    async def _extract_text_from_pdf(self, paper_id: str, pdf_url: str, max_retries: int = 2) -> Optional[Tuple[str, int]]:
        """
        Extract text content from a PDF URL and count words.
        
        Args:
            paper_id: Paper ID
            pdf_url: PDF URL
            max_retries: Number of download retries, default is 2
            
        Returns:
            A tuple (extracted text content, word count) or None (if extraction fails)
        """
        start_time = time.time()
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    logger.info(f"Attempting to download PDF for {paper_id} (attempt {retry_count} of {max_retries})")
                else:
                    logger.info(f"Starting to download PDF for {paper_id}")
                
                # Set a reasonable timeout, for example 60 seconds
                async with aiohttp.ClientSession() as session:
                    async with session.get(pdf_url) as response:
                        if response.status != 200:
                            logger.error(f"Download failed for {paper_id} ({pdf_url}), status code: {response.status}")
                            if retry_count < max_retries:
                                retry_count += 1
                                await asyncio.sleep(2)  # Wait 2 seconds before retrying
                                continue
                            return None
                        
                        pdf_content = await response.read()
                        if not pdf_content or len(pdf_content) < 1000:  # Check if PDF content is too small
                            logger.warning(f"PDF content may be incomplete for {paper_id}, size only {len(pdf_content)} bytes")
                            if retry_count < max_retries:
                                retry_count += 1
                                await asyncio.sleep(2)  # Wait 2 seconds before retrying
                                continue
                        
                        download_time = time.time() - start_time
                        logger.info(f"PDF download completed for {paper_id}, size: {len(pdf_content)/1024:.1f} KB, time: {download_time:.2f} seconds")
                
                # Use PyMuPDF to extract text
                extraction_start = time.time()
                try:
                    # Ensure PDF content is valid
                    if len(pdf_content) < 100:
                        logger.error(f"PDF content too small, likely not a valid PDF for {paper_id}, size: {len(pdf_content)} bytes")
                        if retry_count < max_retries:
                            retry_count += 1
                            await asyncio.sleep(2)  # Wait 2 seconds before retrying
                            continue
                    
                    # Add memory usage hint and strategy for handling large PDFs
                    # PyMuPDF is usually memory efficient, but very large files can still cause problems
                    with fitz.open(stream=pdf_content, filetype="pdf") as doc:
                        total_pages = len(doc)
                        logger.info(f"PDF has {total_pages} pages for {paper_id}")
                        
                        if total_pages == 0:
                            logger.error(f"PDF has no pages for {paper_id}")
                            if retry_count < max_retries:
                                retry_count += 1
                                await asyncio.sleep(2)  # Wait 2 seconds before retrying
                                continue
                        
                        # Extract first N pages (for example 15 pages)
                        pages_to_process = min(15, total_pages)  # Limit to 15 pages max
                        extracted_texts = []
                        
                        for i in range(pages_to_process):
                            try:
                                page = doc.load_page(i)
                                page_text = page.get_text("text")
                                # Immediately clean each page's null bytes
                                page_text = page_text.replace('\x00', '') 
                                
                                # Only add pages that have meaningful content
                                if page_text and len(page_text.strip()) > 10:  
                                    extracted_texts.append(page_text.strip()) 
                            except Exception as page_error:
                                logger.warning(f"Error extracting PDF page {i+1}/{total_pages} for {paper_id}: {page_error}")
                                continue # Skip problem pages
                                
                        # Join all pages with double newlines to separate
                        text = "\n\n".join(extracted_texts)
                    
                    # Check if text was successfully extracted
                    if not text or len(text) < 100:
                        logger.warning(f"Extracted text too short for {paper_id}, length: {len(text)} characters")
                        if retry_count < max_retries:
                            retry_count += 1
                            continue
                    
                    extraction_time = time.time() - extraction_start
                    logger.info(f"PDF text extraction completed for {paper_id}, extracted {pages_to_process}/{total_pages} pages, time: {extraction_time:.2f} seconds")
                    
                    # Note: Text cleaning (clean_text_for_api) is now handled by llm_service
                    # Text length limitation is also moved to llm_service
                    
                    total_time = time.time() - start_time
                    logger.info(f"PDF processing completed for {paper_id} ({pdf_url}), total time: {total_time:.2f} seconds, extracted text length: {len(text)} characters")
                    
                    # Calculate word count after joining pages
                    word_count = len(text.split())
                    
                    return (text, word_count)
                    
                except fitz.FileDataError as fe:
                    logger.error(f"PyMuPDF unable to open or process PDF data for {paper_id}: {fe}")
                    if retry_count < max_retries:
                        retry_count += 1
                        continue
                    return None
                except Exception as e_fitz:
                    logger.error(f"PyMuPDF text extraction error for {paper_id}: {e_fitz.__class__.__name__} - {e_fitz}")
                    if retry_count < max_retries:
                        retry_count += 1
                        continue
                    return None
                    
            except asyncio.TimeoutError:
                 logger.error(f"Download PDF timeout for {paper_id} ({pdf_url})")
                 if retry_count < max_retries:
                     retry_count += 1
                     await asyncio.sleep(2)  # Wait 2 seconds before retrying
                     continue
                 return None
            except aiohttp.ClientError as e_http:
                 logger.error(f"Download PDF client error for {paper_id} ({pdf_url}): {e_http}")
                 if retry_count < max_retries:
                     retry_count += 1
                     await asyncio.sleep(2)  # Wait 2 seconds before retrying
                     continue
                 return None
            except Exception as e_main:
                logger.error(f"Unexpected error occurred during PDF text extraction for {paper_id} ({pdf_url}): {e_main}")
                if retry_count < max_retries:
                    retry_count += 1
                    await asyncio.sleep(2)  # Wait 2 seconds before retrying
                    continue
                return None
                
        # If all retries failed
        logger.error(f"Failed to extract PDF text for {paper_id} after {max_retries} attempts")
        return None
    
    async def _generate_llm_analysis_json(self, paper_id: str, text: str) -> Optional[str]:
        """
        Prepare text, build prompt, call the general LLM service and get the raw JSON response string.
        """
        # 1. Clean text (using functions in this file)
        cleaned_text = clean_text_for_api(text)
        
        # 2. Check and truncate text length
        if not cleaned_text or len(cleaned_text) < 50:
             logger.warning(f"Paper {paper_id} cleaned text is too short or empty, cannot analyze.")
             return None
             
        if len(cleaned_text) > self.max_llm_input_chars:
             logger.warning(f"Paper {paper_id} cleaned text length {len(cleaned_text)} exceeds limit {self.max_llm_input_chars}, truncating")
             cleaned_text = cleaned_text[:self.max_llm_input_chars] + "... [Input Truncated]"
        
        # 3. Build Prompt and Messages (defined here now)
        system_prompt = "You are an expert academic paper analyst, focused on providing objective, accurate, and strictly JSON-formatted paper analysis. All JSON fields must be simple strings, never nested objects or arrays."
        user_prompt = f"""Please analyze the following paper content and provide a structured analysis.

Paper Content:
{cleaned_text}

Please provide analysis in the following aspects:
1. Summary: Brief overview of the paper's main content and contributions.
2. Key Findings: List the main findings and conclusions of the paper.
3. Contributions: What are the paper's main contributions to the field?
4. Methodology: What methods were used in the paper?
5. Limitations: What are the limitations of the paper's methods or results?
6. Future Work: What future research directions does the paper suggest?
7. Keywords: Extract 5-10 important technical keywords or phrases from the paper. Focus on specific technical terms, methods, datasets, or concepts that best represent the paper's content.

Please output the result strictly in JSON format without any explanatory text or prefix, following this structure:
{{
  "summary": "Paper summary",
  "key_findings": "Key findings",
  "contributions": "Main contributions",
  "methodology": "Methodology used",
  "limitations": "Limitations",
  "future_work": "Future work",
  "keywords": "keyword1, keyword2, keyword3, ..."
}}

IMPORTANT: Each field must be a simple string. Use line breaks within the string for lists if needed.
For keywords, provide a comma-separated list.
If any aspect is not explicitly mentioned, mark it as "Not explicitly mentioned"."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 4. Call the general LLM service
        try:
            logger.info(f"Calling LLM service for analysis: {paper_id} (text length: {len(cleaned_text)}) ")
            completion = await llm_service.get_chat_completion(
                messages=messages,
                # Use default model, temperature, max_tokens from llm_service, but specify JSON output
                response_format={"type": "json_object"} 
            )
            
            # 5. Process the response
            if completion and completion.choices and completion.choices[0].message:
                response_content = completion.choices[0].message.content
                if response_content:
                    logger.info(f"Successfully received analysis response from LLM for {paper_id}")
                    return response_content
                else:
                    logger.error(f"LLM response content is empty for {paper_id}")
                    return None
            else:
                logger.error(f"Unable to extract valid content from LLM response for {paper_id}")
                if completion:
                     logger.debug(f"Raw LLM response object for {paper_id}: {completion.model_dump_json()}")
                return None
                
        except Exception as e:
             # Handle potential errors during the call or response processing within this service
             logger.error(f"Error when calling LLM or processing its response for {paper_id}: {e.__class__.__name__} - {e}")
             return None

    async def analyze_paper(self, paper_id: str, timeout_seconds: int = 240) -> Optional[PaperAnalysis]:
        """
        Analyze a single paper: Get information -> Extract text -> Call LLM -> Parse results -> Save analysis
        
        Args:
            paper_id: Paper ID
            timeout_seconds: Timeout for analyzing a single paper (seconds), default 2 minutes
        """
        logger.info(f"[{paper_id}] Starting paper analysis")
        paper_start_time = time.time()
        
        # Set task timeout control
        try:
            return await asyncio.wait_for(
                self._analyze_paper_internal(paper_id),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(f"[{paper_id}] Analysis timeout, exceeded the {timeout_seconds} second limit")
            return None
        except Exception as e:
            logger.error(f"[{paper_id}] Error during analysis process: {e}", exc_info=True)
            return None
        finally:
            paper_duration = time.time() - paper_start_time
            logger.info(f"[{paper_id}] Analysis task completed, total time: {paper_duration:.2f} seconds")
    
    async def _analyze_paper_internal(self, paper_id: str) -> Optional[PaperAnalysis]:
        """Internal method that actually executes the paper analysis logic"""
        # 1. Check if analysis already exists
        existing_analysis = await db_service.get_paper_analysis(paper_id)
        if existing_analysis:
            logger.info(f"[{paper_id}] Analysis already exists, skipping")
            return existing_analysis
        
        # 2. Get paper information (need PDF URL)
        paper = await db_service.get_paper_by_id(paper_id)
        if not paper:
            logger.error(f"[{paper_id}] Paper not found, cannot analyze")
            return None
        if not paper.pdf_url:
             logger.error(f"[{paper_id}] Missing PDF URL, cannot analyze")
             return None

        # 3. Extract PDF text and word count
        logger.info(f"[{paper_id}] Starting PDF text extraction: {paper.pdf_url}")
        extraction_result = await self._extract_text_from_pdf(paper_id, paper.pdf_url)
        
        if extraction_result is None:
            logger.error(f"[{paper_id}] Failed to extract PDF text")
            return None
        
        extracted_text, word_count = extraction_result # Unpack the tuple
        logger.info(f"[{paper_id}] PDF text extraction completed, length: {len(extracted_text)} characters, word count: {word_count}")
        
        # Removed: No longer saving text to database
        if not extracted_text:
            logger.warning(f"[{paper_id}] Extracted text is empty, stopping analysis")
            return None
        
        # 5. Call LLM service to generate analysis JSON string
        logger.info(f"[{paper_id}] Starting LLM service call to generate analysis...")
        analysis_json_string = await self._generate_llm_analysis_json(paper_id, extracted_text)
        if not analysis_json_string:
             logger.error(f"[{paper_id}] LLM failed to generate analysis JSON")
             return None
             
        # 6. Parse and clean LLM returned JSON
        logger.info(f"[{paper_id}] Starting to parse and clean LLM response...")
        cleaned_analysis_data = _parse_and_clean_llm_response(analysis_json_string, paper_id)
        if not cleaned_analysis_data:
             logger.error(f"[{paper_id}] Failed to parse or clean LLM analysis results")
             return None
             
        # 7. Create PaperAnalysis object
        logger.info(f"[{paper_id}] Preparing to create analysis object...")
        try:
            now = datetime.now()
            new_analysis = PaperAnalysis(
                paper_id=paper_id,
                summary=cleaned_analysis_data.get("summary"),
                key_findings=cleaned_analysis_data.get("key_findings"),
                contributions=cleaned_analysis_data.get("contributions"),
                methodology=cleaned_analysis_data.get("methodology"),
                limitations=cleaned_analysis_data.get("limitations"),
                future_work=cleaned_analysis_data.get("future_work"),
                keywords=cleaned_analysis_data.get("keywords"),
                created_at=now,
                updated_at=now
            )
        except Exception as e:
             logger.error(f"[{paper_id}] Failed to create PaperAnalysis object: {e}", exc_info=True)
             return None

        # 8. Save analysis results to database
        logger.info(f"[{paper_id}] Attempting to save final analysis results to database...")
        save_analysis_success = await db_service.save_paper_analysis(new_analysis)
        if save_analysis_success:
            logger.info(f"[{paper_id}] Successfully saved analysis results to database")
            return new_analysis
        else:
            logger.error(f"[{paper_id}] Failed to save analysis results to database")
            return None
            
    async def analyze_pending_papers(self, process_all: bool = False, max_papers: int = None, max_concurrency: int = 2) -> Dict[str, Any]:
        """
        Analyze a batch of pending papers
        
        Args:
            process_all: Whether to process all pending papers without batch size limit
            max_papers: Maximum number of papers to process (if set)
            max_concurrency: Maximum number of concurrent paper analyses
        """
        if self.is_analyzing:
            logger.info("Analysis task is already running")
            return {"status": "already_running", "message": "Analysis task is already running.", "task_id": str(self.current_task.get_name() if self.current_task else None)}

        self.is_analyzing = True
        start_time = time.time()
        processed_count = 0
        failed_count = 0
        total_pending = 0
        total_processed = 0
        
        try:
            # Set batch size and maximum number of papers to process
            batch_limit = None if process_all else self.batch_size
            if max_papers is not None:
                batch_limit = min(max_papers, batch_limit) if batch_limit else max_papers
                
            logger.info(f"Starting analysis task: {'Processing all pending papers' if process_all else f'Batch size={batch_limit}'}, Maximum concurrency: {max_concurrency}")
            
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_concurrency)
            
            # Wrap analysis function, use semaphore to limit concurrency
            async def analyze_with_semaphore(paper_id):
                async with semaphore:
                    logger.info(f"Getting semaphore to analyze paper: {paper_id}")
                    return await self.analyze_paper(paper_id, timeout_seconds=120)
            
            # First get pending papers to analyze
            pending_papers = await db_service.get_papers_without_analysis(limit=batch_limit)
            
            if not pending_papers:
                logger.info("No papers found needing analysis")
                return {"status": "no_pending", "message": "No papers found needing analysis.", "processed": 0, "failed": 0}
            
            while pending_papers:
                batch_size = len(pending_papers)
                total_pending += batch_size
                logger.info(f"Starting new batch: {batch_size} papers to analyze (concurrency limit: {max_concurrency})")
                
                analysis_tasks = []
                for paper in pending_papers:
                    # Use semaphore-wrapped analysis task
                    analysis_tasks.append(analyze_with_semaphore(paper.paper_id))
                
                # Concurrent execution of analysis tasks (but limited by semaphore)
                results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                
                # Process results
                batch_processed = 0
                batch_failed = 0
                for result in results:
                    if isinstance(result, PaperAnalysis):
                        batch_processed += 1
                        processed_count += 1
                    elif isinstance(result, Exception):
                        logger.error(f"Error encountered in batch analysis: {result}")
                        batch_failed += 1
                        failed_count += 1
                    else: # Analysis failed returns None
                        batch_failed += 1
                        failed_count += 1
                
                total_processed += batch_size
                logger.info(f"Current batch completed. Success: {batch_processed}, Failed: {batch_failed}")
                
                # If not processing all papers or reached maximum number, exit loop
                if not process_all or (max_papers is not None and total_processed >= max_papers):
                    break
                    
                # Get next batch of papers to analyze
                if process_all:
                    next_batch_limit = max_papers - total_processed if max_papers is not None else None
                    if next_batch_limit is not None and next_batch_limit <= 0:
                        break
                    pending_papers = await db_service.get_papers_without_analysis(limit=next_batch_limit)
                else:
                    break
            
            duration = time.time() - start_time
            logger.info(f"Analysis task completed. Total time: {duration:.2f} seconds. Total papers: {total_pending}, Success: {processed_count}, Failed: {failed_count}")
            
            return {
                "status": "completed", 
                "message": f"Analysis finished.",
                "total_pending": total_pending,
                "processed": processed_count, 
                "failed": failed_count,
                "duration_seconds": round(duration, 2)
            }
            
        except Exception as e:
            logger.error(f"Analysis task failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "processed": processed_count, "failed": failed_count}
        finally:
            self.is_analyzing = False
            self.current_task = None

# Create global service instance
paper_analysis_service = PaperAnalysisService() 