import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from dotenv import load_dotenv
import logging
import pathlib

# Load environment variables
load_dotenv()


from app.api import paper, search, user

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
api_app.include_router(user.router, prefix="/user", tags=["user"])

# Mount API sub-application to main application
app.mount("/api", api_app)

# Mount pdfjs directory (if exists)
PDFJS_DIR = os.path.join(FRONTEND_DIST_DIR, "pdfjs")
if os.path.exists(PDFJS_DIR) and os.path.isdir(PDFJS_DIR):
    logger.info(f"Mounting pdfjs directory: {PDFJS_DIR}")
    app.mount("/pdfjs", StaticFiles(directory=PDFJS_DIR), name="pdfjs")

# Mount frontend assets directory
ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")
if os.path.exists(ASSETS_DIR) and os.path.isdir(ASSETS_DIR):
    logger.info(f"Mounting assets directory: {ASSETS_DIR}")
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

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
    # API requests should not reach here because we've mounted the API sub-application
    if request.url.path.startswith("/api/"):
        logger.warning(f"API request reached wildcard route: {request.url.path}")
        return {"error": "API route does not exist", "path": request.url.path}
    
    # Check if the requested file exists directly (e.g., favicon.ico)
    requested_file = os.path.join(FRONTEND_DIST_DIR, full_path)
    if os.path.exists(requested_file) and os.path.isfile(requested_file):
        return FileResponse(requested_file)
    
    # Otherwise return index.html (SPA routing)
    index_file = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    else:
        logger.error(f"index.html file does not exist: {index_file}")
        raise HTTPException(status_code=404, detail="Frontend files not found")

# Application startup and shutdown events