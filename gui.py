import os
import sys

# CRITICAL: Define default env variables before importing app modules,
# so Pydantic settings validation passes when running without a .env file.
os.environ["SECRET_KEY"] = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./gym_erp_db.db")

# Force PyInstaller's static graph analyzer to include dynamic packages
import aiosqlite
import passlib.handlers.bcrypt

import threading
import time
import uvicorn
import webview
from app.main import app

def start_fastapi():
    """ Runs the uvicorn loop in a background daemon thread. """
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    print("[DESKTOP] Launching Sport Time Gym ERP wrapper...")
    
    # 1. Spawn FastAPI in background
    server_thread = threading.Thread(target=start_fastapi, daemon=True)
    server_thread.start()
    
    # 2. Bounded wait for binding
    time.sleep(1.2)
    
    # 3. Create native desktop frame
    print("[DESKTOP] Starting native Webview shell window pointing to http://127.0.0.1:8000")
    webview.create_window(
        title="Sport Time Gym - ERP Control Center",
        url="http://127.0.0.1:8000",
        width=1366,
        height=850,
        resizable=True
    )
    
    # 4. Block on UI loop
    webview.start()
