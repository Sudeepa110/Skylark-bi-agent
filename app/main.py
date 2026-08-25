"""
app/main.py
FastAPI Application Server for the Monday.com Executive BI Agent.
Exposes REST and chat endpoints, board explorer API, health diagnostics, and serves the Single-Page UI.
Includes comprehensive error handling for authentication, network, rate limits, and missing boards.
"""

import os
import time
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.monday_client import (
    monday_client,
    MondayError,
    MondayAuthError,
    MondayBoardNotFoundError,
    MondayRateLimitError,
    MondayNetworkError
)
from app.agent import agent
from app.leadership_update import LeadershipUpdateGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_server")

app = FastAPI(
    title="Monday.com Business Intelligence Agent",
    description="Founder-level conversational BI agent querying Deals and Work Orders boards live from Monday.com with live TTS and resilient error handling.",
    version="1.1.0"
)

# CORS middleware for local development & cross-origin deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLERS
# -----------------------------------------------------------------------------

@app.exception_handler(MondayAuthError)
async def monday_auth_exception_handler(request: Request, exc: MondayAuthError):
    logger.error(f"Authentication Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error_type": "AUTHENTICATION_FAILED",
            "message": str(exc),
            "resolution": "Please verify that your MONDAY_TOKEN in .env is valid and has read permissions."
        }
    )

@app.exception_handler(MondayBoardNotFoundError)
async def monday_board_not_found_handler(request: Request, exc: MondayBoardNotFoundError):
    logger.error(f"Board Not Found Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_type": "BOARD_NOT_FOUND",
            "message": str(exc),
            "resolution": "Verify board names in Monday.com ('Deal funnel Data' and 'Work_Order_Tracker Data') or check DEALS_BOARD_ID and WORK_ORDERS_BOARD_ID in .env."
        }
    )

@app.exception_handler(MondayRateLimitError)
async def monday_rate_limit_handler(request: Request, exc: MondayRateLimitError):
    logger.error(f"Rate Limit Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error_type": "RATE_LIMIT_EXCEEDED",
            "message": str(exc),
            "resolution": "Monday.com API complexity limit exceeded. The agent will automatically back off and retry in a few seconds."
        }
    )

@app.exception_handler(MondayNetworkError)
async def monday_network_handler(request: Request, exc: MondayNetworkError):
    logger.error(f"Network Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error_type": "NETWORK_UNAVAILABLE",
            "message": str(exc),
            "resolution": "Unable to connect to Monday.com. Check internet connection."
        }
    )

# -----------------------------------------------------------------------------
# REQUEST / RESPONSE SCHEMAS
# -----------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    force_refresh: Optional[bool] = False

class ChatResponse(BaseModel):
    type: str
    content: str
    suggested_options: List[dict] = []
    caveats: List[str] = []
    timestamp: float = time.time()

# -----------------------------------------------------------------------------
# API ROUTES
# -----------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Verify live connectivity to Monday.com API v2 and board readiness."""
    try:
        conn = monday_client.test_connection()
        boards = monday_client.discover_boards()
        return {
            "status": "healthy" if conn.get("status") == "connected" else "degraded",
            "monday_connection": conn,
            "discovered_boards": boards,
            "cache_ttl_seconds": settings.cache_ttl_seconds,
            "last_sync_time": monday_client.last_sync_time
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "help": "Verify MONDAY_TOKEN and workspace access."
            }
        )

@app.get("/api/boards")
async def get_boards_summary():
    """Retrieve summary metadata and record counts for both boards."""
    try:
        engine, deals_dq, wo_dq = agent.load_data_and_engine()
        pipeline = engine.get_pipeline_summary()
        ops = engine.get_operations_summary()
        return {
            "deals": {
                "total_records": len(engine.df_deals),
                "total_pipeline_val": pipeline["formatted_total_pipeline"],
                "weighted_val": pipeline["formatted_weighted_pipeline"],
                "data_quality": deals_dq
            },
            "work_orders": {
                "total_records": len(engine.df_wo),
                "total_po_val": ops["formatted_total_po_excl"],
                "billed_rev": ops["formatted_total_billed_excl"],
                "unbilled_backlog": ops["formatted_total_unbilled_excl"],
                "data_quality": wo_dq
            },
            "last_sync_time": monday_client.last_sync_time
        }
    except MondayError as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching boards summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load board analytics: {str(e)}")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Process a founder natural language query with ambiguity detection, exact BI calculations, and DQ flags."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Query message cannot be empty.")
        
    try:
        res = agent.answer_query(req.message.strip(), force_refresh=req.force_refresh)
        return ChatResponse(
            type=res.get("type", "answer"),
            content=res.get("content", ""),
            suggested_options=res.get("suggested_options", []),
            caveats=res.get("caveats", [])
        )
    except MondayError as e:
        raise e
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        return ChatResponse(
            type="error",
            content=f"⚠️ **Processing Error**: {str(e)}\n\nPlease verify your Monday board connection or retry in a moment.",
            suggested_options=[
                {"label": "🔄 Sync Live Monday Data", "query": "prepare this week's leadership update"}
            ],
            caveats=[]
        )

@app.get("/api/leadership-update")
async def get_leadership_update(force_refresh: bool = False):
    """Generate and return the formatted executive leadership briefing."""
    try:
        engine, deals_dq, wo_dq = agent.load_data_and_engine(force_refresh=force_refresh)
        gen = LeadershipUpdateGenerator(engine, deals_dq, wo_dq)
        report = gen.generate_leadership_update()
        caveats = agent.cleaner.generate_dq_caveats(deals_dq, wo_dq)
        return {
            "status": "success",
            "report_markdown": report,
            "caveats": caveats
        }
    except MondayError as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating leadership update: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate leadership briefing: {str(e)}")

@app.post("/api/refresh")
async def refresh_cache():
    """Force-refresh live data from Monday.com boards."""
    try:
        engine, deals_dq, wo_dq = agent.load_data_and_engine(force_refresh=True)
        return {
            "status": "refreshed",
            "deals_count": len(engine.df_deals),
            "work_orders_count": len(engine.df_wo),
            "timestamp": time.time()
        }
    except MondayError as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")

@app.get("/api/board-items")
async def get_board_items(board: str = "deals", limit: int = 150):
    """Return structured records for the live board data explorer tab."""
    try:
        engine, deals_dq, wo_dq = agent.load_data_and_engine()
        if board.lower() == "deals":
            cols_to_keep = [c for c in ["name", "client_code", "owner_code", "sector", "deal_stage", "deal_status", "closure_probability", "masked_deal_value", "tentative_close_dt", "actual_close_dt"] if c in engine.df_deals.columns]
            df = engine.df_deals[cols_to_keep].head(limit) if cols_to_keep else engine.df_deals.head(limit)
            return {
                "board": "deals",
                "total": len(engine.df_deals),
                "items": df.fillna("").to_dict(orient="records"),
                "columns": cols_to_keep or list(df.columns)
            }
        else:
            cols_to_keep = [c for c in ["serial_no", "customer_code", "name", "sector", "execution_status", "amount_excl_gst", "billed_excl_gst", "unbilled_excl_gst", "collected_incl_gst", "amount_receivable", "ar_priority"] if c in engine.df_wo.columns]
            df = engine.df_wo[cols_to_keep].head(limit) if cols_to_keep else engine.df_wo.head(limit)
            return {
                "board": "work_orders",
                "total": len(engine.df_wo),
                "items": df.fillna("").to_dict(orient="records"),
                "columns": cols_to_keep or list(df.columns)
            }
    except MondayError as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching board items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount static frontend assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Monday.com BI Agent API is active</h1><p>Static UI loading...</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
