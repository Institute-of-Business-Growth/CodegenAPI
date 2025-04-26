import os
import time
import asyncio
from fastapi import FastAPI, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from codegen import Agent # Assuming Task is part of the SDK
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# --- Configuration & Initialization ---

load_dotenv() # Load environment variables from .env for local dev

# Read configuration from environment variables
CODEGEN_ORG_ID = os.getenv("CODEGEN_ORG_ID")
CODEGEN_API_TOKEN = os.getenv("CODEGEN_API_TOKEN")
APP_API_KEY = os.getenv("APP_API_KEY")

# Basic validation
if not all([CODEGEN_ORG_ID, CODEGEN_API_TOKEN, APP_API_KEY]):
    raise RuntimeError(
        "Missing required environment variables: "
        "CODEGEN_ORG_ID, CODEGEN_API_TOKEN, APP_API_KEY"
    )

# Initialize Codegen Agent (outside endpoint for reuse)
try:
    agent = Agent(org_id=CODEGEN_ORG_ID, token=CODEGEN_API_TOKEN)
except Exception as e:
    # Handle potential initialization errors (e.g., invalid credentials)
    print(f"Error initializing Codegen Agent: {e}")
    # Depending on severity, you might want to exit or prevent app startup
    raise RuntimeError(f"Could not initialize Codegen Agent: {e}") from e


app = FastAPI(
    title="Codegen SDK Wrapper",
    description="API to interact with Codegen SWE agents.",
)

# --- Models ---

class CodegenRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to send to the Codegen agent.")

class CodegenResponse(BaseModel):
    status: str = Field(..., description="The final status of the Codegen task (e.g., completed, failed, timeout).")
    result: str | None = Field(None, description="The result from the Codegen agent (if successful).")
    error: str | None = Field(None, description="Error message if the task failed or timed out.")
    task_id: str | None = Field(None, description="The ID of the Codegen task for tracking purposes.")


# --- Security ---

security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to verify the provided Bearer token against the environment variable."""
    if credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication scheme",
        )
    if credentials.credentials != APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return credentials.credentials # Optionally return the key if needed elsewhere

# --- API Endpoint ---

@app.post(
    "/run-agent",
    response_model=CodegenResponse,
    summary="Run a Codegen Agent Task",
    description="Submits a prompt to the Codegen agent and waits for completion.",
    dependencies=[Depends(verify_api_key)], # Apply API key security
)
async def run_codegen_agent(request: CodegenRequest):
    """
    Takes a prompt, runs the Codegen agent, polls for completion,
    and returns the result or status.
    """
    print(f"Received Codegen request with prompt: '{request.prompt}'")

    try:
        # --- Run Codegen Task ---
        # Assuming agent.run might be synchronous/blocking
        # Run it in a thread pool to avoid blocking the FastAPI event loop
        loop = asyncio.get_event_loop()
        task = await loop.run_in_executor(
            None, agent.run, request.prompt
        )
        print(f"Initial task status: {task.status}, ID: {getattr(task, 'id', 'N/A')}") # Assuming task has an ID

        # --- Polling for Result ---
        start_time = time.time()
        timeout_seconds = 120 # Adjust timeout as needed
        polling_interval_seconds = 3 # Adjust polling frequency

        # Initial task status check
        if task.status == "pending":
            # Wait for task to become active
            while task.status == "pending":
                if time.time() - start_time > timeout_seconds:
                    print("Codegen task timed out while waiting to become active.")
                    return CodegenResponse(status="timeout", error=f"Task timed out after {timeout_seconds} seconds.", task_id=str(getattr(task, 'id', 'N/A')))

                print(f"Polling task status ({task.status})...")
                await asyncio.sleep(polling_interval_seconds)

                # Refresh task status
                await loop.run_in_executor(None, task.refresh)
                
                # If status changes from pending, break out
                if task.status != "pending":
                    break
        
        # If the task has become active (neither pending nor failed/completed)
        if task.status not in ["pending", "completed", "failed"]:
            print(f"Codegen task is now active with status: {task.status}")
            return CodegenResponse(status=task.status, result=f"Task ID: {getattr(task, 'id', 'N/A')} is now active.", task_id=str(getattr(task, 'id', 'N/A')))
        
        # Handle immediate completion or failure
        if task.status == "completed":
            print(f"Codegen task completed. Result: {task.result}")
            return CodegenResponse(status=task.status, result=str(task.result), task_id=str(getattr(task, 'id', 'N/A')))
        elif task.status == "failed":
            print(f"Codegen task failed.")
            error_message = getattr(task, 'error_message', 'Codegen task failed.')
            return CodegenResponse(status=task.status, error=error_message, task_id=str(getattr(task, 'id', 'N/A')))

    except Exception as e:
        print(f"An error occurred during Codegen interaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred: {e}",
        )

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

# --- Optional: Add root path ---
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Codegen SDK Wrapper API is running."}

# --- For local execution ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
# Note: Uvicorn is typically run from the command line, not within the script itself for production.
