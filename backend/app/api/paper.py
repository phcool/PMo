from fastapi import APIRouter, HTTPException, Query, Depends, Path, Header, Body
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import json
import os
import re
import shutil
import oss2
import tempfile
import uuid
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.models.paper import Paper, PaperResponse
from app.services.db_service import db_service
from app.services.arxiv_service import ArxivService
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter()

# OSS配置
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME")

# 创建临时文件存储目录 - 修改为backend目录下
TEMP_PDF_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "temp_pdfs"
TEMP_PDF_DIR.mkdir(exist_ok=True)

# 存储会话和临时文件的映射关系
SESSION_FILES = {}

# 初始化OSS客户端
oss_auth = None
oss_bucket = None

if OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET and OSS_ENDPOINT and OSS_BUCKET_NAME:
    try:
        oss_auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        oss_bucket = oss2.Bucket(oss_auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
        logger.info(f"OSS client initialized for bucket: {OSS_BUCKET_NAME}")
    except Exception as e:
        logger.error(f"Failed to initialize OSS client: {e}")

@router.get("/", response_model=List[PaperResponse])
async def get_papers(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get recent papers (with pagination)
    """
    papers = await db_service.get_recent_papers(limit=limit, offset=offset)
    return papers


@router.get("/count")
async def count_papers():
    """
    Get the total number of papers in the database
    """
    count = await db_service.count_papers()
    return {"count": count}


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: str):
    """
    Get paper by ID
    """
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Convert to response model
    response = PaperResponse(
        paper_id=paper.paper_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        categories=paper.categories,
        pdf_url=paper.pdf_url,
        published_date=paper.published_date,
        updated_at=paper.updated_date
    )
    
    return response

@router.get("/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str):
    """
    获取论文PDF文件的OSS URL或重定向到原始PDF URL
    """
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # 如果OSS客户端初始化失败，直接重定向到原始PDF URL
    if not oss_bucket:
        logger.warning(f"OSS client not initialized. Redirecting to original PDF URL for paper {paper_id}")
        return RedirectResponse(url=paper.pdf_url)
    
    # 确定OSS中的对象键
    # 提取年和月信息
    import re
    year_prefix = ""
    month_prefix = ""
    
    # 处理不同格式的paper_id
    match_new = re.match(r'^(\d{2})(\d{2})\.\d+', paper_id)
    match_old_style_category = re.match(r'^[a-zA-Z\-]+(?:\.[a-zA-Z]{2})?/(\d{2})(\d{2})\d+', paper_id)
    match_old_no_category = re.match(r'^(\d{2})(\d{2})\d{3,}', paper_id)
    
    if match_new:
        year_prefix = match_new.group(1)
        month_prefix = match_new.group(2)
    elif match_old_style_category:
        year_prefix = match_old_style_category.group(1)
        month_prefix = match_old_style_category.group(2)
    elif match_old_no_category:
        year_prefix = match_old_no_category.group(1)
        month_prefix = match_old_no_category.group(2)
    
    # 准备文件名和OSS对象键
    sanitized_paper_id = re.sub(r'[/:.]', '_', paper_id)
    sanitized_file_name = f"{sanitized_paper_id}.pdf"
    
    if year_prefix and month_prefix:
        object_key = f"papers/{year_prefix}/{month_prefix}/{sanitized_file_name}"
    else:
        object_key = f"papers/unknown_date_format/{sanitized_file_name}"
    
    logger.info(f"Checking OSS for paper {paper_id} at key: {object_key}")
    
    try:
        # 检查OSS中是否存在该文件
        if oss_bucket.object_exists(object_key):
            # 生成签名URL，设置10分钟过期时间
            signed_url = oss_bucket.sign_url('GET', object_key, 600)
            logger.info(f"Found paper {paper_id} in OSS, returning signed URL")
            return RedirectResponse(url=signed_url)
        else:
            logger.info(f"Paper {paper_id} not found in OSS, falling back to original URL")
            return RedirectResponse(url=paper.pdf_url)
    except Exception as e:
        logger.error(f"Error accessing OSS for paper {paper_id}: {e}")
        # 出错时回退到原始PDF URL
        return RedirectResponse(url=paper.pdf_url)

@router.get("/recommend/")
async def get_recommended_papers(
    limit: int = Query(30, description="Number of recommended papers"),
    offset: int = Query(0, description="Recommended papers offset"),
    x_user_id: Optional[str] = Header(None, description="User unique identifier")
):
    """
    Get recommended papers based on user profile, or provide random papers from popular categories for new users
    """
    recommended_papers = []
    
    if x_user_id:
        # Try to get personalized recommendations
        recommended_papers = await recommendation_service.recommend_papers(user_id=x_user_id, limit=limit, offset=offset)
        
    # If no personalized recommendation results (possibly new user or insufficient history)
    if not recommended_papers:
        logger.info(f"User {x_user_id or 'anonymous'} has no personalized recommendations, providing random recommendations from popular categories")
        popular_categories = ["cs.CV", "cs.AI", "cs.LG", "cs.CL"]  # Define popular categories
        recommended_papers = await db_service.get_random_papers_by_category(categories=popular_categories, limit=limit, offset=offset)
        
    return recommended_papers 

@router.post("/search")
async def search_papers(
    query: Dict[str, str] = Body(..., description="Search query"),
    limit: int = Query(5, description="Maximum number of results", ge=1, le=20)
):
    """
    Search for papers directly based on a query string
    
    Returns a list of relevant papers that match the query
    """
    try:
        # 从请求体中获取查询文本
        query_text = query.get("query", "")
        
        if not query_text or len(query_text.strip()) == 0:
            return {"papers": []}
            
        logger.info(f"Paper search request with query: '{query_text}'")
        
        # 使用向量搜索获取相关论文
        paper_ids = await vector_search_service.search(query_text, k=limit)
        
        if not paper_ids:
            logger.info(f"No papers found for query: '{query_text}'")
            return {"papers": []}
        
        # 获取论文详细信息
        papers = []
        for paper_id in paper_ids:
            paper = await db_service.get_paper_by_id(paper_id)
            if paper:
                papers.append({
                    "title": paper.title,
                    "authors": paper.authors,
                    "categories": paper.categories,
                    "url": paper.pdf_url or ""
                })
        
        logger.info(f"Found {len(papers)} papers for query: '{query_text}'")
        return {"papers": papers}
        
    except Exception as e:
        logger.error(f"Error searching for papers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching for papers: {str(e)}") 

@router.get("/{paper_id}/view-pdf")
async def view_paper_pdf(paper_id: str, session_id: str = None):
    """
    下载PDF文件到服务器临时目录并提供查看链接
    """
    if not session_id:
        session_id = str(uuid.uuid4())
        
    paper = await db_service.get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # 创建用户会话目录
    session_dir = TEMP_PDF_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    
    # 准备文件名
    sanitized_paper_id = re.sub(r'[/:.]', '_', paper_id)
    temp_file_path = session_dir / f"{sanitized_paper_id}.pdf"
    
    # 如果文件已经存在，直接返回
    if temp_file_path.exists():
        logger.info(f"PDF for paper {paper_id} already exists in temp directory, returning cached file")
        # 记录此会话使用的文件
        if session_id not in SESSION_FILES:
            SESSION_FILES[session_id] = []
        if str(temp_file_path) not in SESSION_FILES[session_id]:
            SESSION_FILES[session_id].append(str(temp_file_path))
        return FileResponse(temp_file_path, media_type="application/pdf")
    
    # 尝试从OSS获取PDF文件
    if oss_bucket:
        try:
            # 确定OSS中的对象键
            year_prefix = ""
            month_prefix = ""
            
            # 处理不同格式的paper_id
            match_new = re.match(r'^(\d{2})(\d{2})\.\d+', paper_id)
            match_old_style_category = re.match(r'^[a-zA-Z\-]+(?:\.[a-zA-Z]{2})?/(\d{2})(\d{2})\d+', paper_id)
            match_old_no_category = re.match(r'^(\d{2})(\d{2})\d{3,}', paper_id)
            
            if match_new:
                year_prefix = match_new.group(1)
                month_prefix = match_new.group(2)
            elif match_old_style_category:
                year_prefix = match_old_style_category.group(1)
                month_prefix = match_old_style_category.group(2)
            elif match_old_no_category:
                year_prefix = match_old_no_category.group(1)
                month_prefix = match_old_no_category.group(2)
            
            sanitized_file_name = f"{sanitized_paper_id}.pdf"
            
            if year_prefix and month_prefix:
                object_key = f"papers/{year_prefix}/{month_prefix}/{sanitized_file_name}"
            else:
                object_key = f"papers/unknown_date_format/{sanitized_file_name}"
            
            logger.info(f"Checking OSS for paper {paper_id} at key: {object_key}")
            
            # 检查OSS中是否存在该文件
            if oss_bucket.object_exists(object_key):
                # 下载到临时文件
                logger.info(f"Downloading PDF from OSS to temp directory: {temp_file_path}")
                result = oss_bucket.get_object_to_file(object_key, str(temp_file_path))
                
                # 记录此会话使用的文件
                if session_id not in SESSION_FILES:
                    SESSION_FILES[session_id] = []
                SESSION_FILES[session_id].append(str(temp_file_path))
                
                return FileResponse(temp_file_path, media_type="application/pdf")
            else:
                logger.info(f"Paper {paper_id} not found in OSS, downloading from original URL")
        except Exception as e:
            logger.error(f"Error accessing OSS for paper {paper_id}: {e}")
    
    # 如果OSS获取失败，尝试从原始URL下载
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            logger.info(f"Downloading PDF from original URL: {paper.pdf_url}")
            async with session.get(paper.pdf_url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(temp_file_path, 'wb') as f:
                        f.write(content)
                    
                    # 记录此会话使用的文件
                    if session_id not in SESSION_FILES:
                        SESSION_FILES[session_id] = []
                    SESSION_FILES[session_id].append(str(temp_file_path))
                    
                    return FileResponse(temp_file_path, media_type="application/pdf")
                else:
                    logger.error(f"Failed to download PDF from {paper.pdf_url}, status: {response.status}")
                    # 如果无法下载，回退到原始URL
                    return RedirectResponse(url=paper.pdf_url)
    except Exception as e:
        logger.error(f"Error downloading PDF from original URL: {e}")
        # 出错时回退到原始PDF URL
        return RedirectResponse(url=paper.pdf_url)

@router.delete("/cleanup-session/{session_id}")
async def cleanup_session_files(session_id: str):
    """
    清理会话相关的临时文件
    """
    if session_id not in SESSION_FILES:
        return {"status": "success", "message": "No files to clean up"}
    
    try:
        files_cleaned = 0
        for file_path in SESSION_FILES[session_id]:
            if os.path.exists(file_path):
                os.remove(file_path)
                files_cleaned += 1
        
        # 尝试删除会话目录
        session_dir = TEMP_PDF_DIR / session_id
        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
            except:
                pass
        
        # 清理会话记录
        del SESSION_FILES[session_id]
        
        return {
            "status": "success", 
            "message": f"Cleaned up {files_cleaned} files for session {session_id}"
        }
    except Exception as e:
        logger.error(f"Error cleaning up session files: {e}")
        return {"status": "error", "message": str(e)} 