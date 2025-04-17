import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 确保设置了Hugging Face镜像站点
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from app.api import paper, search, scheduler
from app.services.scheduler_service import scheduler_service

# 配置日志
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
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

# 包含路由
app.include_router(paper.router, prefix="/api/papers", tags=["papers"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])

@app.get("/")
async def root():
    return {"message": "Welcome to DL Paper Monitor API"}

# 应用启动和停止事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
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