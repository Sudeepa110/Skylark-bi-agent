"""
seed_monday_boards.py
Creates and populates the 'Deals' and 'Work Orders' boards in monday.com
using the live Monday.com GraphQL API v2 with automatic rate-limit retry.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

MONDAY_TOKEN = os.environ.get(
    "MONDAY_TOKEN",
    "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY5NjU3Mzc3OCwiYWFpIjoxMSwidWlkIjoxMTQzMTQwMjQsImlhZCI6IjIwMjYtMDgtMjVUMDQ6NDM6MjIuNzA1WiIsInBlciI6Im1lOndyaXRlIiwiYWN0aWQiOjM2NjAyNDM4LCJyZ24iOiJhcHNlMiJ9.kCU2-yUe1z-zGZEACelKjhGL51gZXrMGCzIbOeFF5Kc"
)
WORKSPACE_ID = 3364949

DEAL_FILE = r"C:\Users\sudee\Downloads\Deal funnel Data.xlsx"
WO_FILE = r"C:\Users\sudee\Downloads\Work_Order_Tracker Data.xlsx"

HEADERS = {
    "Authorization": MONDAY_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2024-10"
}

def gql_request(query: str, variables: dict = None, max_retries: int = 5):
    data = {"query": query}
    if variables:
        data["variables"] = variables
    data_bytes = json.dumps(data).encode("utf-8")
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request("https://api.monday.com/v2", data=data_bytes, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "errors" in res:
                    msgs = [e.get("message", "") for e in res["errors"]]
                    if any("complexity" in m.lower() or "rate limit" in m.lower() for m in msgs):
                        time.sleep((2 ** attempt) + 1)
                        continue
                    raise Exception(f"Monday API Error: {res['errors']}")
                return res.get("data", {})
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code in (500, 502, 503, 504):
                sleep_time = (2 ** attempt) + 2
                print(f"[RateLimit/HTTP {e.code}] Retrying in {sleep_time}s...", flush=True)
                time.sleep(sleep_time)
            else:
                raise e
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1 + attempt)
    raise Exception("Exceeded max retries for request")

def get_existing_boards():
    res = gql_request("{ boards (workspace_ids: [%d]) { id name } }" % WORKSPACE_ID)
    return {b["name"]: b["id"] for b in res.get("boards", [])}

def get_board_columns(board_id: str):
    res = gql_request("{ boards (ids: [%s]) { columns { id title type } } }" % board_id)
    cols = res["boards"][0]["columns"]
    return {c["title"]: c["id"] for c in cols}

def create_board(name: str) -> str:
    query = """
    mutation ($name: String!, $workspaceId: ID!) {
        create_board (board_name: $name, board_kind: public, workspace_id: $workspaceId) {
            id
            name
        }
    }
    """
    res = gql_request(query, {"name": name, "workspaceId": str(WORKSPACE_ID)})
    board_id = res["create_board"]["id"]
    print(f"Created board '{name}' with ID: {board_id}", flush=True)
    return board_id

def create_column(board_id: str, title: str, col_type: str) -> str:
    query = """
    mutation ($boardId: ID!, $title: String!, $colType: ColumnType!) {
        create_column (board_id: $boardId, title: $title, column_type: $colType) {
            id
            title
        }
    }
    """
    try:
        res = gql_request(query, {"boardId": str(board_id), "title": title, "colType": col_type})
        col_id = res["create_column"]["id"]
        print(f"  Created column '{title}' ({col_type}) -> ID: {col_id}", flush=True)
        return col_id
    except Exception as e:
        print(f"  Warning creating column '{title}': {e}", flush=True)
        return None

def delete_default_items(board_id: str):
    try:
        items_res = gql_request("{ boards (ids: [%s]) { items_page (limit: 10) { items { id name } } } }" % board_id)
        items = items_res["boards"][0]["items_page"]["items"]
        for itm in items:
            if "Item" in itm["name"] or "Sample" in itm["name"]:
                gql_request("mutation { delete_item (item_id: %s) { id } }" % itm["id"])
    except Exception as e:
        pass

def insert_single_item(board_id: str, item_name: str, col_vals: dict):
    query = """
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (board_id: $boardId, item_name: $itemName, column_values: $columnValues) {
            id
        }
    }
    """
    return gql_request(query, {
        "boardId": str(board_id),
        "itemName": item_name,
        "columnValues": json.dumps(col_vals)
    })

def seed_deals():
    print("\n=== SEEDING DEALS BOARD ===", flush=True)
    df = pd.read_excel(DEAL_FILE)
    
    existing = get_existing_boards()
    if "Deals" in existing:
        board_id = existing["Deals"]
        print(f"Board 'Deals' exists (ID: {board_id})", flush=True)
    else:
        board_id = create_board("Deals")
        time.sleep(1)
        cols_to_add = [
            ("Owner code", "text"),
            ("Client Code", "text"),
            ("Deal Status", "text"),
            ("Close Date (A)", "text"),
            ("Closure Probability", "text"),
            ("Masked Deal value", "numbers"),
            ("Tentative Close Date", "text"),
            ("Deal Stage", "text"),
            ("Product deal", "text"),
            ("Sector/service", "text"),
            ("Created Date", "text")
        ]
        for title, ctype in cols_to_add:
            create_column(board_id, title, ctype)
            time.sleep(0.3)
            
    col_map = get_board_columns(board_id)
    
    items_res = gql_request("{ boards (ids: [%s]) { items_page (limit: 500) { items { id name } } } }" % board_id)
    items = items_res["boards"][0]["items_page"]["items"]
    if len(items) >= len(df) - 5:
        print(f"Deals board already has {len(items)} items. Skipping.", flush=True)
        return board_id

    delete_default_items(board_id)
    tasks = []
    for idx, row in df.iterrows():
        item_name = str(row.get("Deal Name") or f"Deal #{idx+1}").strip()
        if item_name == "nan" or not item_name:
            item_name = f"Deal #{idx+1}"
        col_vals = {}
        for col_name in df.columns:
            if col_name == "Deal Name":
                continue
            val = row.get(col_name)
            if pd.isna(val):
                continue
            col_id = col_map.get(col_name)
            if not col_id:
                continue
            if isinstance(val, (datetime, pd.Timestamp)):
                col_vals[col_id] = val.strftime("%Y-%m-%d")
            elif col_name == "Masked Deal value":
                try:
                    col_vals[col_id] = str(float(val))
                except:
                    col_vals[col_id] = str(val)
            else:
                col_vals[col_id] = str(val)
        tasks.append((idx, item_name, col_vals))

    count = 0
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(insert_single_item, board_id, name, cv): (idx, name) for idx, name, cv in tasks}
        for future in as_completed(futures):
            count += 1
            if count % 50 == 0 or count == len(tasks):
                print(f"  [Deals] Uploaded {count}/{len(tasks)} items...", flush=True)
            time.sleep(0.05)

    return board_id

def seed_work_orders():
    print("\n=== SEEDING WORK ORDERS BOARD ===", flush=True)
    df = pd.read_excel(WO_FILE, header=1)
    print(f"Loaded {len(df)} work order rows from Excel.", flush=True)
    
    existing = get_existing_boards()
    if "Work Orders" in existing:
        board_id = existing["Work Orders"]
        print(f"Board 'Work Orders' exists (ID: {board_id})", flush=True)
    else:
        board_id = create_board("Work Orders")
        time.sleep(1)
        
        cols_to_add = [
            ("Deal name masked", "text"),
            ("Customer Name Code", "text"),
            ("Nature of Work", "text"),
            ("Last executed month of recurring project", "text"),
            ("Execution Status", "text"),
            ("Data Delivery Date", "text"),
            ("Date of PO/LOI", "text"),
            ("Document Type", "text"),
            ("Probable Start Date", "text"),
            ("Probable End Date", "text"),
            ("BD/KAM Personnel code", "text"),
            ("Sector", "text"),
            ("Type of Work", "text"),
            ("Is any Skylark software platform part of the client deliverables in this deal?", "text"),
            ("Last invoice date", "text"),
            ("latest invoice no.", "text"),
            ("Amount in Rupees (Excl of GST) (Masked)", "numbers"),
            ("Amount in Rupees (Incl of GST) (Masked)", "numbers"),
            ("Billed Value in Rupees (Excl of GST.) (Masked)", "numbers"),
            ("Billed Value in Rupees (Incl of GST.) (Masked)", "numbers"),
            ("Collected Amount in Rupees (Incl of GST.) (Masked)", "numbers"),
            ("Amount to be billed in Rs. (Exl. of GST) (Masked)", "numbers"),
            ("Amount to be billed in Rs. (Incl. of GST) (Masked)", "numbers"),
            ("Amount Receivable (Masked)", "numbers"),
            ("AR Priority account", "text"),
            ("Quantity by Ops", "numbers"),
            ("Quantities as per PO", "text"),
            ("Quantity billed (till date)", "numbers"),
            ("Balance in quantity", "numbers"),
            ("Invoice Status", "text"),
            ("Expected Billing Month", "text"),
            ("Actual Billing Month", "text"),
            ("Actual Collection Month", "text"),
            ("WO Status (billed)", "text"),
            ("Collection status", "text"),
            ("Collection Date", "text"),
            ("Billing Status", "text")
        ]
        for title, ctype in cols_to_add:
            create_column(board_id, title, ctype)
            time.sleep(0.3)
            
    col_map = get_board_columns(board_id)
    
    items_res = gql_request("{ boards (ids: [%s]) { items_page (limit: 500) { items { id name } } } }" % board_id)
    items = items_res["boards"][0]["items_page"]["items"]
    if len(items) >= len(df) - 5:
        print(f"Work Orders board already has {len(items)} items. Skipping.", flush=True)
        return board_id

    delete_default_items(board_id)
    print(f"Starting upload of {len(df)} Work Orders...", flush=True)
    
    tasks = []
    for idx, row in df.iterrows():
        item_name = str(row.get("Serial #") or f"WO #{idx+1}").strip()
        if item_name == "nan" or not item_name:
            item_name = f"WO #{idx+1}"
            
        col_vals = {}
        for col_name in df.columns:
            if col_name == "Serial #":
                continue
            val = row.get(col_name)
            if pd.isna(val):
                continue
            col_id = col_map.get(col_name)
            if not col_id:
                continue
                
            if isinstance(val, (datetime, pd.Timestamp)):
                col_vals[col_id] = val.strftime("%Y-%m-%d")
            elif "Amount" in col_name or "Billed" in col_name or "Collected" in col_name or "Quantity" in col_name or "Balance" in col_name:
                try:
                    col_vals[col_id] = str(float(val))
                except:
                    col_vals[col_id] = str(val)
            else:
                col_vals[col_id] = str(val)
                
        tasks.append((idx, item_name, col_vals))

    count = 0
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(insert_single_item, board_id, name, cv): (idx, name) for idx, name, cv in tasks}
        for future in as_completed(futures):
            count += 1
            if count % 25 == 0 or count == len(tasks):
                print(f"  [Work Orders] Uploaded {count}/{len(tasks)} items...", flush=True)
            time.sleep(0.08)

    print(f"Work Orders seeding complete! ({count} items)", flush=True)
    return board_id

if __name__ == "__main__":
    deals_id = seed_deals()
    wo_id = seed_work_orders()
    print(f"\nAll boards seeded successfully!\nDeals Board ID: {deals_id}\nWork Orders Board ID: {wo_id}", flush=True)
