"""
Agent Core Service

Handles:
1. Strands Agent execution
2. Session management (agent pool)
3. Tool execution (MCP clients)
4. SSE streaming
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("=== Agent Core Service Starting ===")
    logger.info("Agent execution engine initialized")

    

    yield

    # Shutdown
    logger.info("=== Agent Core Service Shutting Down ===")
    # TODO: Cleanup agent pool, MCP clients, etc.


# Create FastAPI app with lifespan handler
app = FastAPI(
    title="Strands Agent Chatbot - Agent Core",
    version="2.0.0",
    description="Agent execution and tool orchestration service",
    lifespan=lifespan
)

# Add CORS middleware for local development
# In production (AWS), CloudFront handles routing so CORS is not needed
if os.getenv('ENVIRONMENT', 'development') == 'development':
    logger.info("Adding CORS middleware for local development")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Frontend dev server
            "http://localhost:3001",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Import routers
from routers import health, chat, gateway_tools, tools

# Include routers
app.include_router(health.router)
app.include_router(chat.router)
# app.include_router(gateway_tools.router)
# app.include_router(tools.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
