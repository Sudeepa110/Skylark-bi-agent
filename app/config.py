"""
app/config.py
Configuration and environment variable management for the Monday.com BI Agent.
Reads all credentials purely from environment variables or .env file.
"""

import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    # Monday.com Configuration
    monday_token: str = os.getenv("MONDAY_TOKEN", "")
    workspace_id: int = int(os.getenv("WORKSPACE_ID", "3364949"))
    deals_board_id: str = os.getenv("DEALS_BOARD_ID", "")
    work_orders_board_id: str = os.getenv("WORK_ORDERS_BOARD_ID", "")
    
    # LLM API Configuration
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "120"))

settings = Settings()
