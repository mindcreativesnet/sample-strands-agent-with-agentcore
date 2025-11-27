# Copilot Instructions for Strands Agent Chatbot

This repository contains a production-ready multi-agent conversational AI system built with AWS Bedrock AgentCore and Strands Agents.

## 🏗 Architecture Overview

The system is composed of three main pillars:
1.  **Frontend + BFF (Next.js)**: `chatbot-app/frontend`
    -   Next.js App Router application serving the UI and acting as a Backend-for-Frontend.
    -   Handles authentication (Cognito), session management, and SSE streaming from the runtime.
    -   Communicates with AgentCore Runtime via HTTP/SigV4.
2.  **AgentCore Runtime (Python)**: `chatbot-app/agentcore`
    -   Containerized FastAPI service running the "Strands Agent" orchestration logic.
    -   Manages conversation state, tool execution (Local & Built-in), and memory.
    -   **Entry Point**: `chatbot-app/agentcore/src/main.py`.
3.  **Infrastructure (AWS CDK)**: `agent-blueprint/`
    -   Defines the AWS resources using TypeScript CDK.
    -   **Stacks**: `agentcore-gateway-stack` (MCP tools), `agentcore-runtime-stack` (Agent container), `chatbot-deployment` (Frontend).

## 🛠 Developer Workflows

### Local Development
-   **Setup**: Run `chatbot-app/setup.sh` to install dependencies.
-   **Start**: Run `chatbot-app/start.sh` to launch:
    -   Frontend: `http://localhost:3000`
    -   Agent Runtime: `http://localhost:8000` (or 8080)
-   **Note**: Local runtime still connects to AWS Bedrock for model inference. Ensure AWS credentials are set in `agent-blueprint/.env`.

### Deployment
-   **Deploy All**: `cd agent-blueprint && ./deploy.sh`
-   **Deploy Specific**: `./deploy.sh --frontend`, `./deploy.sh --runtime`, etc.
-   **CDK Context**: Check `cdk.context.json` in respective stack folders for configuration.

### Testing
-   **Integration Tests**: Python scripts in `tests/` (e.g., `test-gateway.py`).
-   **Gateway Tests**: `agent-blueprint/agentcore-gateway-stack/scripts/test-gateway.sh`.

## 🧩 Key Patterns & Conventions

### Agent & Tools
-   **Tool Protocols**:
    -   **Local**: Python functions with `@tool` decorator in `chatbot-app/agentcore/src/local_tools`.
    -   **MCP (Gateway)**: Lambda functions in `agent-blueprint/agentcore-gateway-stack/lambda-functions`. Exposed via AgentCore Gateway.
    -   **Built-in**: AWS SDK calls (e.g., Code Interpreter) managed by the runtime.
-   **Tool Filtering**: Tools are dynamically filtered based on user selection in the UI (`agent.py`).

### Frontend (Next.js)
-   **Streaming**: Uses Server-Sent Events (SSE) for real-time agent responses.
-   **Config**: Tool configuration is in `chatbot-app/frontend/src/config/tools-config.json`.
-   **Styling**: Tailwind CSS with `shadcn/ui` components.

### Infrastructure (CDK)
-   **Modular Stacks**: Infrastructure is split into separate stacks for Gateway, Runtime, and Frontend to allow independent updates.
-   **Lambda Functions**: Defined in `agent-blueprint/agentcore-gateway-stack/infrastructure/lib/lambda-stack.ts`.

## ⚠️ Critical Considerations
-   **Authentication**: Service-to-service communication often uses AWS SigV4. Ensure proper IAM roles are defined in CDK stacks.
-   **Memory**: The system uses a two-tier memory system (Session + Long-term). Changes to memory logic should be done in `agent.py` or `turn_based_session_manager.py`.
-   **Environment Variables**: Critical for configuration. See `.env.example` in `agent-blueprint/`.

## 📂 Important Paths
-   **Agent Logic**: `chatbot-app/agentcore/src/agent/`
-   **Tool Definitions**: `chatbot-app/agentcore/src/local_tools/` & `agent-blueprint/agentcore-gateway-stack/lambda-functions/`
-   **CDK Entry**: `agent-blueprint/agentcore-gateway-stack/infrastructure/bin/gateway-stack.ts`
-   **Frontend API**: `chatbot-app/frontend/src/app/api/`
