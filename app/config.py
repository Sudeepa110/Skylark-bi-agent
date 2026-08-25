"""
app/config.py
Configuration and environment variable management for the Monday.com BI Agent.
"""

import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    # Monday.com Configuration
    monday_token: str = os.getenv(
        "MONDAY_TOKEN",
        "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY5NjU3Mzc3OCwiYWFpIjoxMSwidWlkIjoxMTQzMTQwMjQsImlhZCI6IjIwMjYtMDgtMjVUMDQ6NDM6MjIuNzA1WiIsInBlciI6Im1lOndyaXRlIiwiYWN0aWQiOjM2NjAyNDM4LCJyZ24iOiJhcHNlMiJ9.kCU2-yUe1z-zGZEACelKjhGL51gZXrMGCzIbOeFF5Kc"
    )
    workspace_id: int = int(os.getenv("WORKSPACE_ID", "3364949"))
    deals_board_id: str = os.getenv("DEALS_BOARD_ID", "")
    work_orders_board_id: str = os.getenv("WORK_ORDERS_BOARD_ID", "")
    
    # LLM API Configuration
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "120"))

settings = Settings()
