import uvicorn
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    # Get configuration from environment variables or use defaults
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    # In production, set reload=False to avoid unnecessary file monitoring and memory usage
    reload = os.getenv("API_RELOAD", "False").lower() == "true"
    
    # Run the API server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    ) 