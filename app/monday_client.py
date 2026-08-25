"""
app/monday_client.py
Dynamic live client for querying monday.com boards and items via GraphQL API v2.
Features:
- Automatic schema discovery (Deals & Work Orders)
- Cursor-based pagination for large datasets
- Rate-limit handling with exponential backoff
- In-memory caching with configurable TTL and force-refresh
- Stale cache fallback for high availability during network hiccups
- Robust error classification (Auth, RateLimit, BoardNotFound, Network)
- Conversion of board items into structured Pandas DataFrames
"""

import time
import json
import logging
import urllib.request
import urllib.error
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from app.config import settings

logger = logging.getLogger("monday_client")
logging.basicConfig(level=logging.INFO)

class MondayError(Exception):
    """Base exception for Monday.com operations."""
    pass

class MondayAuthError(MondayError):
    """Raised when authentication fails (401, 403, or invalid token)."""
    pass

class MondayRateLimitError(MondayError):
    """Raised when rate limit or complexity budget is exceeded."""
    pass

class MondayBoardNotFoundError(MondayError):
    """Raised when the requested board ID or workspace is not found."""
    pass

class MondayNetworkError(MondayError):
    """Raised when Monday API is unreachable or times out."""
    pass

class MondayClient:
    def __init__(self, token: Optional[str] = None, workspace_id: Optional[int] = None):
        self.token = token or settings.monday_token
        self.workspace_id = workspace_id or settings.workspace_id
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "API-Version": "2024-10"
        }
        self.api_url = "https://api.monday.com/v2"
        self._board_cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
        self._board_ids: Dict[str, str] = {}
        self.last_sync_time: Optional[float] = None

    def execute_gql(self, query: str, variables: Optional[dict] = None, max_retries: int = 5) -> dict:
        """Execute a GraphQL query with automatic retry on 429 rate limits, complexity errors, and transient network errors."""
        if not self.token or not self.token.strip():
            raise MondayAuthError("MONDAY_TOKEN is missing. Please configure a valid Monday.com API v2 token in your .env file.")

        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        data_bytes = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries):
            req = urllib.request.Request(self.api_url, data=data_bytes, headers=self.headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    if "errors" in result:
                        error_msgs = [e.get("message", "") for e in result["errors"]]
                        full_err = " | ".join(error_msgs)
                        
                        # Complexity / Rate limit
                        if any("complexity" in m.lower() or "rate limit" in m.lower() for m in error_msgs):
                            wait_time = (2 ** attempt) + 1
                            logger.warning(f"Complexity limit hit, waiting {wait_time}s (attempt {attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                            
                        # Authentication error in GraphQL payload
                        if any("not authenticated" in m.lower() or "unauthorized" in m.lower() or "invalid token" in m.lower() for m in error_msgs):
                            raise MondayAuthError(f"Monday API Authentication Failed: {full_err}. Please verify your MONDAY_TOKEN.")

                        raise MondayError(f"Monday GraphQL Error: {full_err}")
                    return result.get("data", {})

            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise MondayAuthError(f"Monday API Auth Error ({e.code}): Invalid or expired API token. Check MONDAY_TOKEN in .env.")
                elif e.code == 429:
                    wait_time = (2 ** attempt) + 2
                    logger.warning(f"HTTP 429 Rate limited, sleeping {wait_time}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                elif e.code in (500, 502, 503, 504):
                    wait_time = (2 ** attempt) + 1
                    logger.warning(f"HTTP {e.code} Server error from Monday.com, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    err_body = e.read().decode("utf-8", errors="ignore")
                    raise MondayError(f"Monday API HTTP {e.code}: {err_body}")

            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                logger.warning(f"Network error communicating with Monday.com: {e} (attempt {attempt+1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise MondayNetworkError(f"Unable to reach Monday.com API: {e}. Check internet connectivity.")
                time.sleep(1 + attempt)

            except Exception as e:
                if attempt == max_retries - 1:
                    raise MondayError(f"Unexpected error in Monday API client: {str(e)}")
                time.sleep(1 + attempt)

        raise MondayRateLimitError("Exceeded maximum retries for Monday API request due to complexity rate limits.")

    def test_connection(self) -> dict:
        """Verify authentication and retrieve user context."""
        try:
            query = "{ me { id name email is_guest } }"
            res = self.execute_gql(query)
            me = res.get("me", {})
            return {
                "status": "connected" if me else "error",
                "user_id": me.get("id"),
                "name": me.get("name"),
                "email": me.get("email")
            }
        except MondayAuthError as e:
            return {"status": "auth_error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def discover_boards(self) -> Dict[str, str]:
        """Dynamically find Deals and Work Orders board IDs in the workspace."""
        query = """
        query {
            boards (limit: 50, state: all) {
                id
                name
                state
            }
        }
        """
        try:
            res = self.execute_gql(query)
            boards = res.get("boards", [])
        except Exception as e:
            logger.warning(f"Failed to query boards dynamically: {e}")
            boards = []

        found = {}
        for b in boards:
            b_name_lower = b["name"].lower().strip()
            if "deal" in b_name_lower:
                found["Deals"] = b["id"]
            elif "work_order" in b_name_lower or "work order" in b_name_lower or "wo" in b_name_lower:
                found["Work Orders"] = b["id"]
                
        # If env variables set, they take precedence
        if settings.deals_board_id:
            found["Deals"] = settings.deals_board_id
        if settings.work_orders_board_id:
            found["Work Orders"] = settings.work_orders_board_id

        self._board_ids = found
        logger.info(f"Discovered boards: {found}")
        return found

    def fetch_board_items(self, board_id: str, force_refresh: bool = False) -> pd.DataFrame:
        """Fetch all items and column values from a board with pagination and stale cache fallback."""
        now = time.time()
        if not force_refresh and board_id in self._board_cache:
            cache_time, cached_df = self._board_cache[board_id]
            if now - cache_time < settings.cache_ttl_seconds:
                logger.info(f"Returning cached board data for {board_id} ({len(cached_df)} rows)")
                return cached_df.copy()

        try:
            # 1. Fetch column titles and types
            col_query = """
            query ($boardId: ID!) {
                boards (ids: [$boardId], state: all) {
                    id
                    name
                    columns {
                        id
                        title
                        type
                    }
                }
            }
            """
            b_res = self.execute_gql(col_query, {"boardId": str(board_id)})
            if not b_res.get("boards"):
                raise MondayBoardNotFoundError(f"Board ID '{board_id}' not found in your Monday.com workspace.")
                
            board_info = b_res["boards"][0]
            board_name = board_info["name"]
            columns = board_info.get("columns", [])
            col_id_to_title = {c["id"]: c["title"] for c in columns}

            # 2. Paginated item fetch
            all_items = []
            cursor = None
            
            while True:
                if cursor:
                    item_query = """
                    query ($boardId: ID!, $cursor: String!) {
                        boards (ids: [$boardId], state: all) {
                            items_page (limit: 100, cursor: $cursor) {
                                cursor
                                items {
                                    id
                                    name
                                    column_values {
                                        id
                                        text
                                        value
                                    }
                                }
                            }
                        }
                    }
                    """
                    page_res = self.execute_gql(item_query, {"boardId": str(board_id), "cursor": cursor})
                else:
                    item_query = """
                    query ($boardId: ID!) {
                        boards (ids: [$boardId], state: all) {
                            items_page (limit: 100) {
                                cursor
                                items {
                                    id
                                    name
                                    column_values {
                                        id
                                        text
                                        value
                                    }
                                }
                            }
                        }
                    }
                    """
                    page_res = self.execute_gql(item_query, {"boardId": str(board_id)})

                page_data = page_res["boards"][0]["items_page"]
                items = page_data.get("items", [])
                all_items.extend(items)
                cursor = page_data.get("cursor")
                if not cursor or len(items) == 0:
                    break

            # 3. Build DataFrame rows
            rows = []
            for itm in all_items:
                row = {"item_id": itm["id"], "name": itm["name"]}
                for cv in itm.get("column_values", []):
                    col_title = col_id_to_title.get(cv["id"], cv["id"])
                    val_text = cv.get("text")
                    if val_text is not None and str(val_text).strip() != "":
                        row[col_title] = str(val_text).strip()
                    elif cv.get("value") is not None:
                        try:
                            raw_v = json.loads(cv["value"])
                            if isinstance(raw_v, dict) and "text" in raw_v:
                                row[col_title] = raw_v["text"]
                            else:
                                row[col_title] = str(raw_v)
                        except:
                            row[col_title] = str(cv["value"])
                    else:
                        row[col_title] = None
                rows.append(row)

            df = pd.DataFrame(rows)
            self._board_cache[board_id] = (now, df)
            self.last_sync_time = now
            logger.info(f"Fetched live board '{board_name}' (ID: {board_id}) with {len(df)} records.")
            return df.copy()

        except Exception as e:
            # Stale cache fallback for high availability
            if board_id in self._board_cache:
                cache_time, cached_df = self._board_cache[board_id]
                logger.warning(f"Live fetch failed ({e}). Gracefully falling back to cached board data from {time.time() - cache_time:.1f}s ago.")
                return cached_df.copy()
            raise e

    def get_deals_and_work_orders(self, force_refresh: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch both Deals and Work Orders boards live from Monday.com with clear missing board errors."""
        if not self._board_ids:
            self.discover_boards()
            
        deals_id = self._board_ids.get("Deals")
        wo_id = self._board_ids.get("Work Orders")
        
        if not deals_id or not wo_id:
            raise MondayBoardNotFoundError(
                f"Could not locate both 'Deals' (found: {deals_id}) and 'Work Orders' (found: {wo_id}) boards in Monday.com. "
                "Please verify that 'Deal funnel Data' and 'Work_Order_Tracker Data' exist in your workspace or set DEALS_BOARD_ID and WORK_ORDERS_BOARD_ID in .env."
            )
            
        df_deals = self.fetch_board_items(deals_id, force_refresh=force_refresh)
        df_wo = self.fetch_board_items(wo_id, force_refresh=force_refresh)
        return df_deals, df_wo

# Global client singleton
monday_client = MondayClient()
