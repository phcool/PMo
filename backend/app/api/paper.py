from fastapi import APIRouter, HTTPException, Query, Depends, Path, Header, Body
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import json
import os
import aiohttp
import oss2

from app.models.paper import Paper, PaperResponse
from app.services.db_service import db_service
from app.services.arxiv_service import ArxivService
from app.services.vector_search_service import vector_search_service
from app.services.recommendation_service import recommendation_service
from app.services.chat_service import chat_service
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)

router = APIRouter()

# OSS配置
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME")

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

@router.post("/download-pdf-for-chat")
async def download_pdf_for_chat(
    paper_id: str = Body(..., description="Paper ID"),
    chat_id: str = Body(..., description="Chat session ID")
):
    """
    Download a paper's PDF from OSS storage and associate it with a chat session.
    """
    try:
        # 检查聊天会话是否存在
        if chat_id not in chat_service.active_chats:
            raise HTTPException(status_code=404, detail=f"Chat session {chat_id} not found")
        
        # 检查论文是否存在
        paper = await db_service.get_paper_by_id(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper with ID {paper_id} not found")
        
        # 检查是否有OSS配置
        if not all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET_NAME]):
            raise HTTPException(status_code=500, detail="OSS storage not properly configured")
        
        # 计算OSS中的对象键
        # 从论文ID中提取年份和月份格式 (YYMM)
        import re
        # 提取年月信息, 适配两种格式: "2303.12345" 或 "arxiv:2303.12345v1"
        match = re.search(r'(\d{2})(\d{2})\.\d+', paper_id)
        
        if match:
            year, month = match.groups()
            # 构建OSS中的对象路径
            sanitized_paper_id = paper_id.split(':')[-1].split('v')[0].strip()
            object_key = f"papers/{year}/{month}/{sanitized_paper_id}.pdf"
        else:
            # 如果无法解析年月，使用直接路径
            sanitized_paper_id = paper_id.split(':')[-1].split('v')[0].strip()
            object_key = f"papers/{sanitized_paper_id}.pdf"
        
        logger.info(f"Attempting to download paper PDF from OSS: {object_key}")
        
        # 初始化OSS客户端
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
        
        # 检查对象是否存在
        try:
            if not bucket.object_exists(object_key):
                # 如果找不到按照新的路径格式存储的PDF，尝试旧格式
                old_object_key = f"papers/{sanitized_paper_id}/{sanitized_paper_id}.pdf"
                if not bucket.object_exists(old_object_key):
                    raise HTTPException(status_code=404, detail=f"PDF for paper {paper_id} not found in OSS storage")
                object_key = old_object_key
        except oss2.exceptions.OssError as e:
            logger.error(f"OSS error checking object existence: {str(e)}")
            raise HTTPException(status_code=500, detail=f"OSS error: {str(e)}")
        
        # 下载PDF文件
        try:
            pdf_object = bucket.get_object(object_key)
            pdf_content = pdf_object.read()
            logger.info(f"Successfully downloaded PDF for {paper_id} from OSS ({len(pdf_content)} bytes)")
        except oss2.exceptions.OssError as e:
            logger.error(f"OSS error downloading PDF: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to download PDF from OSS: {str(e)}")
        
        # 保存PDF并将其与会话关联
        filename = f"{paper_id}.pdf"
        success = await chat_service.process_pdf(chat_id, pdf_content, filename)
        
        if not success:
            raise HTTPException(
                status_code=422,
                detail="Failed to process PDF file. This could be due to file format issues or API limitations."
            )
        
        # 获取文件信息
        file_info = None
        if chat_id in chat_service.active_chats and "files" in chat_service.active_chats[chat_id]:
            files = chat_service.active_chats[chat_id]["files"]
            if files:
                # 获取最后添加的文件
                latest_file = files[-1]
                file_info = {
                    "id": latest_file.get("id", ""),
                    "name": filename,
                    "size": len(pdf_content),
                    "upload_time": datetime.now().isoformat()
                }
        
        return {
            "success": True,
            "message": f"PDF for paper {paper_id} successfully downloaded and associated with chat session",
            "file_info": file_info
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing PDF download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}") 