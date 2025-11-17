# AgentCore Integration Guide

This document explains how AWS Bedrock AgentCore is used in this chatbot platform.

## What is AgentCore?

AWS Bedrock AgentCore is a managed service for deploying containerized AI agents:
- **Runtime**: Managed container execution environment (dedicated AWS service)
- **Memory**: DynamoDB-backed conversation persistence
- **Gateway**: SigV4-authenticated tool access via Lambda

**Key Documentation**:
- Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- Memory: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
- Gateway: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html

## How AgentCore is Used

### 1. AgentCore Runtime

**Location**: `chatbot-app/agentcore/`

The Strands Agent is containerized and deployed as an AgentCore Runtime:

```python
# chatbot-app/agentcore/src/agent/agent.py
from strands import Agent
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

class ChatbotAgent:
    def __init__(self, session_id: str, user_id: str):
        self.agent = Agent(
            model=BedrockModel(model_id="claude-sonnet-4"),
            tools=[...],
            session_manager=AgentCoreMemorySessionManager(...)  # AgentCore Memory
        )
```

**Key Features**:
- Runs on AWS Bedrock AgentCore managed runtime (not Fargate/ECS)
- Integrated with AgentCore Memory for conversation persistence
- Turn-based session management to optimize API calls
- Local tools (Weather, Visualization, etc.) embedded in container

**Deployment**:
```bash
cd agent-blueprint/agentcore-runtime-stack
cdk deploy
```

### 2. AgentCore Memory

**Type**: DynamoDB-backed conversation storage

AgentCore Memory automatically persists conversation history:

```python
# Automatic persistence via AgentCoreMemorySessionManager
memory_config = AgentCoreMemoryConfig(
    memory_arn="arn:aws:bedrock-agentcore:...:memory/mem-xxx",
    max_tokens=12000
)

session_manager = AgentCoreMemorySessionManager(
    session_id=session_id,
    memory_config=memory_config
)
```

**Benefits**:
- Conversation history persisted across sessions
- Cross-session user preferences retained
- Automatic token limit management
- DynamoDB on-demand pricing

**No Manual Setup Required**: Memory is created automatically when Runtime is deployed.

### 3. AgentCore Gateway

**Location**: `agent-blueprint/agentcore-gateway-stack/`

AgentCore Gateway provides SigV4-authenticated access to Lambda tools:

```
AgentCore Runtime (with SigV4 credentials)
           ↓
   AgentCore Gateway (AWS_IAM auth)
           ↓
   ┌──────┴───────┬────────┬─────────┬─────────┐
   ↓              ↓        ↓         ↓         ↓
Wikipedia      ArXiv    Google   Tavily    Finance
Lambda         Lambda   Lambda   Lambda    Lambda
```

**Gateway Configuration**:
```python
# chatbot-app/agentcore/src/agent/gateway_mcp_client.py
from bedrock_agentcore.gateway.client import GatewayClient

gateway_client = GatewayClient(
    gateway_id="gw-xxx",
    region="us-west-2",
    # SigV4 auth automatic via IAM role
)

tools = gateway_client.list_tools()
# Returns: wikipedia_search, arxiv_search, google_web_search, etc.
```

**Benefits**:
- Secure access to external services (no credentials in Runtime)
- Centralized API key management via Secrets Manager
- Lambda-based tools with auto-scaling
- Pay-per-invocation pricing

**Deployment**:
```bash
cd agent-blueprint/agentcore-gateway-stack
./scripts/deploy.sh
```

### 4. AgentCore Runtime-to-Runtime (A2A)

**Location**: `agent-blueprint/agentcore-runtime-a2a-stack/report-writer/`

Optional: Deploy additional AgentCore Runtimes that communicate via A2A protocol:

```
Main Runtime (Chat Agent)
      ↓ A2A call
Report Writer Runtime (Document Generation)
      ↓
  S3 Bucket (Generated DOCX files)
```

**Use Case**: Specialized agents for complex workflows (report generation, data analysis, etc.)

**Deployment**:
```bash
cd agent-blueprint/agentcore-runtime-a2a-stack/report-writer
./deploy.sh
```

## Architecture Comparison

### Without AgentCore (Traditional)
```
Frontend → Backend (FastAPI)
              ↓
          Strands Agent (local process)
              ↓
          Manual session management
          Manual memory persistence (files/DB)
          Direct Lambda invocations
```

**Issues**:
- Manual container orchestration (ECS/Fargate)
- Custom memory implementation required
- No built-in tracing/metrics
- Lambda access via API keys in environment

### With AgentCore (This Project)
```
Frontend+BFF → AgentCore Runtime (AWS Bedrock managed)
                    ↓
                Strands Agent + AgentCore Memory
                    ↓
                AgentCore Gateway (SigV4)
                    ↓
                Lambda Functions
```

**Benefits**:
- Managed container lifecycle (AWS Bedrock AgentCore service)
- Built-in DynamoDB memory integration
- SigV4-secured Gateway access
- A2A communication support

## When to Use AgentCore

### Use AgentCore When:
- You need built-in conversation memory across sessions
- You want managed container orchestration
- You require SigV4-secured tool access
- You plan to use A2A communication

### Skip AgentCore When:
- You're building a simple prototype
- You don't need persistent memory
- You prefer full control over infrastructure

## Key Files

| File | Purpose |
|------|---------|
| `chatbot-app/agentcore/src/agent/agent.py` | Main agent with AgentCore Memory integration |
| `chatbot-app/agentcore/src/agent/turn_based_session_manager.py` | Optimized memory persistence |
| `chatbot-app/agentcore/src/agent/gateway_mcp_client.py` | Gateway tool access |
| `agent-blueprint/agentcore-runtime-stack/` | Runtime deployment (CDK) |
| `agent-blueprint/agentcore-gateway-stack/` | Gateway + Lambda functions (CDK) |

## Further Reading

- AWS Bedrock AgentCore Documentation: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/
- AgentCore Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- AgentCore Memory: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
- AgentCore Gateway: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html
- Strands Agents Framework: https://github.com/anthropics/strands-agents

---

For implementation details, see:
- **README.md**: Architecture overview and features
- **DEPLOYMENT.md**: Step-by-step deployment instructions
