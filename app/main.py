# main.py (or your main FastAPI application file)
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.health import health_check

# Import your LLMProvider and logger
from llms.llm_provider import LLMProvider  # Adjust path if necessary
import threading
from utils.logger import get_logger       # Adjust path if necessary
# 1. Import the SlackService CLASS directly from your module
from services.slack_service import SlackService # <--- CORRECTED IMPORT
import logging

# Get a logger for startup messages
startup_logger = get_logger("fastapi_lifecycle")

# --- FastAPI Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on application startup
    startup_logger.info("Application starting up...")
    
    # Initialize LLMProvider
    llm_provider = LLMProvider() # This will now use your custom logger internally

    # --- Test Gemini Connection (Primary Focus) ---
    startup_logger.info("Performing Gemini LLM connection test...")
    gemini_operational = llm_provider.test_llm_connection(model_provider="gemini")
    if gemini_operational:
        startup_logger.info("Gemini LLM connection test SUCCEEDED.")
    else:
        startup_logger.critical("CRITICAL: Gemini LLM connection test FAILED. Gemini-dependent features may not work.")
        # You could choose to raise an exception here to prevent startup if Gemini is essential:
        # raise RuntimeError("Gemini LLM failed startup health check.")

    # --- Optionally Test OpenAI Connection ---
    # Check if OpenAI API key is configured before attempting to test
    if llm_provider.openai_api_key:
        startup_logger.info("Performing OpenAI LLM connection test (API key found)...")
        openai_operational = llm_provider.test_llm_connection(model_provider="openai")
        if openai_operational:
            startup_logger.info("OpenAI LLM connection test SUCCEEDED.")
        else:
            startup_logger.warning("WARNING: OpenAI LLM connection test FAILED. OpenAI-dependent features may not work.")
    else:
        startup_logger.info("Skipping OpenAI LLM connection test: OPENAI_API_KEY not configured.")
        
    startup_logger.info("Application startup checks complete.")
    slack_bot_instance = None # Define here for broader scope in case of errors

    try:
        # 2. Create an INSTANCE of the SlackService class
        slack_bot_instance = SlackService() 
        
        print("[FastAPI Lifespan] Launching Slack listener thread...")
        # 3. The target for the thread is the 'start' method of your SlackService INSTANCE.
        slack_thread = threading.Thread(target=slack_bot_instance.start, daemon=True)
        slack_thread.start()
        print("[FastAPI Lifespan] Slack listener thread started successfully.")
        
    except Exception as e:
        print(f"[FastAPI Lifespan] CRITICAL ERROR initializing or starting Slack Service: {e}")
        import traceback
        traceback.print_exc()
        # Depending on severity, you might want to prevent FastAPI from starting
        # or handle this error more gracefully.
    yield
    # Code to run on application shutdown
    startup_logger.info("Application shutting down...")

# Initialize FastAPI app with the lifespan manager
app = FastAPI(
    title="Cipher Pol",
    description="Core backend service for internal agent integration.",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Your API Routes and other application logic would go here ---
# Example:
# @app.get("/")
# async def read_root():
#     return {"message": "API is running"}

if __name__ == "__main__":
    import uvicorn
    # This is for local development running; your deployment might handle this differently
    uvicorn.run(app, host="0.0.0.0", port=8000)