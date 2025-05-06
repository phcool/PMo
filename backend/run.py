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
    
    # 在生产环境中，设置reload=False以避免不必要的文件监控和内存使用
    reload = os.getenv("API_RELOAD", "False").lower() == "true"
    
    # Run the API server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    ) 