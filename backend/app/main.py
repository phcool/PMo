import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from dotenv import load_dotenv
import logging
import pathlib

# 加载环境变量
load_dotenv()

# 确保设置了Hugging Face镜像站点
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from app.api import paper, search, scheduler, user
from app.services.scheduler_service import scheduler_service

# 配置日志
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# 获取前端dist目录的绝对路径
FRONTEND_DIST_DIR = os.getenv("FRONTEND_DIST_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist"))
logger.info(f"使用前端静态文件目录: {FRONTEND_DIST_DIR}")

# 创建API子应用
api_app = FastAPI(
    title="DL Paper Monitor API",
    description="A Deep Learning Paper Collection and Search Service API",
    version="0.1.0"
)

# 主应用
app = FastAPI(
    title="DL Paper Monitor",
    description="A Deep Learning Paper Collection and Search Service",
    version="0.1.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应替换为特定来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由 - 使用正确的前缀
api_app.include_router(paper.router, prefix="/papers", tags=["papers"])
api_app.include_router(search.router, prefix="/search", tags=["search"])
api_app.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
api_app.include_router(user.router, prefix="/user", tags=["user"])

# 将API子应用挂载到主应用
app.mount("/api", api_app)

# 挂载pdfjs目录（如果存在）
PDFJS_DIR = os.path.join(FRONTEND_DIST_DIR, "pdfjs")
if os.path.exists(PDFJS_DIR) and os.path.isdir(PDFJS_DIR):
    logger.info(f"挂载pdfjs目录: {PDFJS_DIR}")
    app.mount("/pdfjs", StaticFiles(directory=PDFJS_DIR), name="pdfjs")

# 挂载前端assets目录
ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")
if os.path.exists(ASSETS_DIR) and os.path.isdir(ASSETS_DIR):
    logger.info(f"挂载assets目录: {ASSETS_DIR}")
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

# 根路由 - 返回前端首页
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Welcome to DL Paper Monitor API"}

# 处理SPA前端路由 - 确保不会拦截API请求
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    # API请求不应该走到这里，因为我们已经挂载了API子应用
    if request.url.path.startswith("/api/"):
        logger.warning(f"API请求走到了通配符路由: {request.url.path}")
        return {"error": "API路由不存在", "path": request.url.path}
    
    # 检查请求的文件是否直接存在（比如favicon.ico等）
    requested_file = os.path.join(FRONTEND_DIST_DIR, full_path)
    if os.path.exists(requested_file) and os.path.isfile(requested_file):
        return FileResponse(requested_file)
    
    # 否则返回index.html（SPA路由处理）
    index_file = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        logger.error(f"index.html文件不存在: {index_file}")
        raise HTTPException(status_code=404, detail="前端文件未找到")

# 应用启动和停止事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 检查前端目录是否存在
    if not os.path.exists(FRONTEND_DIST_DIR):
        logger.error(f"前端目录不存在: {FRONTEND_DIST_DIR}")
    elif not os.path.exists(os.path.join(FRONTEND_DIST_DIR, "index.html")):
        logger.error(f"index.html文件不存在: {os.path.join(FRONTEND_DIST_DIR, 'index.html')}")
    
    # 检查是否禁用调度器（当使用cron作业时）
    disable_scheduler = os.getenv("DISABLE_SCHEDULER", "false").lower() == "true"
    if disable_scheduler:
        logger.info("调度器已被禁用（DISABLE_SCHEDULER=true），使用cron作业代替")
        return
        
    # 自动启动论文定时获取任务
    auto_start = os.getenv("AUTO_START_SCHEDULER", "true").lower() == "true"
    if auto_start:
        logger.info("正在启动论文定时获取任务...")
        scheduler_service.start()
        logger.info("论文定时获取任务已启动")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    # 停止定时任务
    if scheduler_service.is_running:
        logger.info("正在停止论文定时获取任务...")
        scheduler_service.stop() 
        logger.info("论文定时获取任务已停止")