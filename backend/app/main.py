import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from dotenv import load_dotenv
import logging
import pathlib

# Load environment variables
load_dotenv()


from app.api import paper, search, chat

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Get absolute path to frontend dist directory
FRONTEND_DIST_DIR = os.getenv("FRONTEND_DIST_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist"))
logger.info(f"Using frontend static files directory: {FRONTEND_DIST_DIR}")

# Create API sub-application
api_app = FastAPI(
    title="DL Paper Monitor API",
    version="0.1.0"
)

# Main application
app = FastAPI(
    title="DL Paper Monitor",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be replaced with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes - using correct prefixes
api_app.include_router(paper.router, prefix="/papers", tags=["papers"])
api_app.include_router(search.router, prefix="/search", tags=["search"])
api_app.include_router(chat.router, prefix="/chat", tags=["chat"])

# Mount API sub-application to main application
app.mount("/api", api_app)

# Mount frontend assets directory
ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")
if os.path.exists(ASSETS_DIR) and os.path.isdir(ASSETS_DIR):
    logger.info(f"Mounting assets directory: {ASSETS_DIR}")
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR, html=True), name="assets")

# Mount favicon and other static files at root level if they exist
for static_file in ["favicon.ico"]:
    file_path = os.path.join(FRONTEND_DIST_DIR, static_file)
    if os.path.exists(file_path):
        logger.info(f"Serving static file at root: {static_file}")
        @app.get(f"/{static_file}", include_in_schema=False)
        async def serve_static_file():
            return FileResponse(file_path)

# Root route - return frontend homepage
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Welcome to DL Paper Monitor API"}

# Handle SPA frontend routing - ensure API requests are not intercepted
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    # API请求不应该到达这里，因为我们已经挂载了API子应用
    if request.url.path.startswith("/api/"):
        logger.warning(f"API request reached wildcard route: {request.url.path}")
        return {"error": "API route does not exist", "path": request.url.path}
    
    # 如果是assets目录下的请求，尝试提供静态文件
    if full_path.startswith("assets/"):
        # 尝试使用精确路径
        requested_file = os.path.join(FRONTEND_DIST_DIR, full_path)
        if os.path.exists(requested_file) and os.path.isfile(requested_file):
            logger.info(f"Serving asset file: {full_path}")
            return FileResponse(requested_file)
        
        # 如果找不到精确的文件，尝试基于前缀匹配
        asset_dir = os.path.dirname(requested_file)
        if not os.path.exists(asset_dir):
            logger.warning(f"Asset directory not found: {asset_dir}")
            return HTMLResponse(status_code=404, content="Asset directory not found")
            
        try:
            # 获取文件名的基本部分（没有哈希和扩展名）
            filename_parts = os.path.basename(requested_file).split('.')
            name_part = filename_parts[0].split('-')[0]  # 例如从 'index-99db0f8c.js' 获取 'index'
            ext_part = filename_parts[-1]  # 获取扩展名
            
            logger.info(f"Looking for asset with name: {name_part} and extension: {ext_part}")
            
            # 在assets目录中找到所有匹配前缀和扩展名的文件
            for file in os.listdir(asset_dir):
                file_parts = file.split('.')
                if len(file_parts) > 1 and file_parts[-1] == ext_part and file.startswith(name_part):
                    logger.info(f"Found matching asset: {file} for request: {full_path}")
                    return FileResponse(os.path.join(asset_dir, file))
        except Exception as e:
            logger.error(f"Error finding matching asset: {e}")
    
    # PDF.js映射文件处理
    if full_path.endswith('.map'):
        # 忽略源映射文件请求，直接返回空内容
        # 这些仅用于开发调试，不影响生产使用
        return Response(content="", media_type="application/json")
    
    # 检查请求的文件是否直接存在（例如favicon.ico）
    requested_file = os.path.join(FRONTEND_DIST_DIR, full_path)
    if os.path.exists(requested_file) and os.path.isfile(requested_file):
        return FileResponse(requested_file)
    
    # 否则返回index.html（SPA路由）
    index_file = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        logger.error(f"index.html file does not exist: {index_file}")
        raise HTTPException(status_code=404, detail="Frontend files not found")

# Application startup and shutdown events