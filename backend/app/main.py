import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging



from app.api import paper, search, chat, user

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create API sub-application
api_app = FastAPI()

# Main application
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
api_app.include_router(paper.router, prefix="/papers", tags=["papers"])
api_app.include_router(search.router, prefix="/search", tags=["search"])
api_app.include_router(chat.router, prefix="/chat", tags=["chat"])
api_app.include_router(user.router, prefix="/user", tags=["user"])

# Mount API sub-application to main application
app.mount("/api", api_app)


