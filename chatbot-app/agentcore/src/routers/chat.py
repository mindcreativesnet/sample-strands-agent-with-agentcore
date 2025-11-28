"""Chat router - handles agent execution and SSE streaming
Implements AgentCore Runtime standard endpoints:
- POST /invocations (required)
- GET /ping (required)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from agent.agent import ChatbotAgent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# AgentCore Runtime Standard Request/Response Models
class InvocationInput(BaseModel):
    """Input for /invocations endpoint"""
    user_id: str
    session_id: str
    message: str



class InvocationRequest(BaseModel):
    """AgentCore Runtime standard request format"""
    input: InvocationInput


class InvocationResponse(BaseModel):
    """AgentCore Runtime standard response format"""
    output: Dict[str, Any]

def get_agent(
    session_id: str,
    user_id: Optional[str] = None,
) -> ChatbotAgent:
    """
    Create agent instance with current configuration for session

    No caching - creates new agent each time to reflect latest configuration.
    Session message history is managed by AgentCore Memory automatically.
    """
    logger.info(f"Creating agent for session {session_id}, user {user_id or 'anonymous'}")
    
    # Create agent with AgentCore Memory - messages and preferences automatically loaded/saved
    agent = ChatbotAgent(
        session_id=session_id,
        user_id=user_id,
    )

    return agent


# ============================================================
# AgentCore Runtime Standard Endpoints (REQUIRED)
# ============================================================

@router.get("/ping")
async def ping():
    """Health check endpoint (required by AgentCore Runtime)"""
    return {"status": "healthy"}


@router.post("/invocations")
async def invocations(request: InvocationRequest):
    """
    AgentCore Runtime standard invocation endpoint (required)

    Supports user-specific tool filtering and SSE streaming.
    Creates/caches agent instance per session + tool configuration.
    """
    input_data = request.input
    logger.info(f"Invocation request - Session: {input_data.session_id}, User: {input_data.user_id}")
    logger.info(f"Message: {input_data.message[:50]}...")

    try:
        # Get agent instance with user-specific configuration
        # AgentCore Memory tracks preferences across sessions per user_id
        agent = get_agent(
            session_id=input_data.session_id,
            user_id=input_data.user_id,
        )

        # Stream response from agent as SSE (with optional files)
        return StreamingResponse(
            agent.stream_async(
                input_data.message,
                session_id=input_data.session_id
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-ID": input_data.session_id
            }
        )

    except Exception as e:
        logger.error(f"Error in invocations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}"
        )

