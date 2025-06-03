from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
import threading

# Assuming your api.health router is correctly set up
from api import health as health_router

# 1. Import the SlackService CLASS directly from your module
from services.slack_service import SlackService # <--- CORRECTED IMPORT
import logging

logging.basicConfig(
    level=logging.DEBUG,  # This is the key change
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    print("[FastAPI Lifespan] Initializing Slack Service...")
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
    
    # Shutdown actions (optional cleanup)
    print("[FastAPI Lifespan] FastAPI shutdown. Slack thread is a daemon and will exit with the main thread.")
    # If you had specific cleanup for the slack_service_instance, you could call it here.
    # For example: if slack_bot_instance and hasattr(slack_bot_instance, 'stop'): 
    #    print("[FastAPI Lifespan] Attempting to stop Slack service...")
    #    slack_bot_instance.stop() # (You would need to implement a 'stop' method in SlackService)


app = FastAPI(
    title="Cipher Pol",
    description="Core backend service for internal agent integration.",
    version="0.1.0",
    lifespan=lifespan,
)

# Include your API routers
app.include_router(health_router.router)

@app.get("/")
async def read_root():
    return {"message": "Cipher Pol agent service is currently operational"}

if __name__ == "__main__":
    print("Starting FastAPI application with Uvicorn...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
