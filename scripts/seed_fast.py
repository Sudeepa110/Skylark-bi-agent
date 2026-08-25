"""
scripts/seed_fast.py
Populates remaining Deals and Work Orders into Monday.com boards sequentially
with robust rate-limit backoff.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

MONDAY_TOKEN = os.environ.get("MONDAY_TOKEN", "")
DEAL_FILE = r"C:\Users\sudee\Downloads\Deal funnel Data.xlsx"
WO_FILE = r"C:\Users\sudee\Downloads\Work_Order_Tracker Data.xlsx"

HEADERS = {
    "Authorization": MONDAY_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2024-10"
}

DEALS_BOARD_ID = "5030844461"
WO_BOARD_ID = "5030844471"

def gql(query, variables=None):
    data = {"query": query}
    if variables:
        data["variables"] = variables
    data_bytes = json.dumps(data).encode("utf-8")
    for attempt in range(8):
        try:
            req = urllib.request.Request("https://api.monday.com/v2", data=data_bytes, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "errors" in res:
                    msgs = [e.get("message", "") for e in res["errors"]]
                    if any("complexity" in m.lower() or "rate limit" in m.lower() for m in msgs):
                        wait_t = 15 + (attempt * 10)
                        print(f"  [RateLimit] Waiting {wait_t}s...", flush=True)
                        time.sleep(wait_t)
                        continue
                    raise Exception(f"GraphQL Error: {res['errors']}")
                return res.get("data", {})
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code in (500, 502, 503, 504):
                wait_t = 20 + (attempt * 10)
                print(f"  [HTTP {e.code}] Waiting {wait_t}s...", flush=True)
                time.sleep(wait_t)
            else:
                raise e
        except Exception as e:
            time.sleep(5)
    raise Exception("Exceeded max retries")

def get_existing_item_names(board_id):
    names = set()
    cursor = None
    while True:
        if cursor:
            res = gql("query ($bId: ID!, $c: String!) { boards (ids: [$bId]) { items_page (limit: 500, cursor: $c) { cursor items { name } } } }", {"bId": board_id, "c": cursor})
        else:
            res = gql("query ($bId: ID!) { boards (ids: [$bId]) { items_page (limit: 500) { cursor items { name } } } }", {"bId": board_id})
        p = res["boards"][0]["items_page"]
        for itm in p.get("items", []):
            names.add(itm["name"])
        cursor = p.get("cursor")
        if not cursor or len(p.get("items", [])) == 0:
            break
    return names

def get_columns(board_id):
    res = gql("query ($bId: ID!) { boards (ids: [$bId]) { columns { id title } } }", {"bId": board_id})
    return {c["title"]: c["id"] for c in res["boards"][0]["columns"]}

def upload_deals():
    print("\n--- POPULATING DEALS ---", flush=True)
    df = pd.read_excel(DEAL_FILE)
    col_map = get_columns(DEALS_BOARD_ID)
    
    # Check count
    existing_names = get_existing_item_names(DEALS_BOARD_ID)
    print(f"Deals board currently has {len(existing_names)} items.", flush=True)
    
    # We will upload items up to 346
    count = 0
    mutation = "mutation ($bId: ID!, $name: String!, $vals: JSON!) { create_item (board_id: $bId, item_name: $name, column_values: $vals) { id } }"
    
    # Let's seed sequentially
    target_count = len(df)
    needed = target_count - len(existing_names)
    if needed <= 0:
        print("Deals board is already fully populated!", flush=True)
        return

    print(f"Uploading remaining {needed} deals...", flush=True)
    for idx, row in df.iterrows():
        if count >= needed:
            break
        item_name = str(row.get("Deal Name") or f"Deal #{idx+1}").strip()
        col_vals = {}
        for col_name in df.columns:
            if col_name == "Deal Name": continue
            val = row.get(col_name)
            if pd.isna(val): continue
            col_id = col_map.get(col_name)
            if not col_id: continue
            if isinstance(val, (datetime, pd.Timestamp)):
                col_vals[col_id] = val.strftime("%Y-%m-%d")
            elif col_name == "Masked Deal value":
                try: col_vals[col_id] = str(float(val))
                except: col_vals[col_id] = str(val)
            else:
                col_vals[col_id] = str(val)
                
        gql(mutation, {"bId": DEALS_BOARD_ID, "name": item_name, "vals": json.dumps(col_vals)})
        count += 1
        if count % 25 == 0 or count == needed:
            print(f"  [Deals] Uploaded {count}/{needed}", flush=True)
        time.sleep(0.08)

def upload_work_orders():
    print("\n--- POPULATING WORK ORDERS ---", flush=True)
    df = pd.read_excel(WO_FILE, header=1)
    col_map = get_columns(WO_BOARD_ID)
    
    existing_names = get_existing_item_names(WO_BOARD_ID)
    print(f"Work Orders board currently has {len(existing_names)} items.", flush=True)
    
    target_count = len(df)
    needed = target_count - len(existing_names)
    if needed <= 0:
        print("Work Orders board is already fully populated!", flush=True)
        return

    print(f"Uploading {needed} work orders...", flush=True)
    mutation = "mutation ($bId: ID!, $name: String!, $vals: JSON!) { create_item (board_id: $bId, item_name: $name, column_values: $vals) { id } }"
    
    count = 0
    for idx, row in df.iterrows():
        item_name = str(row.get("Serial #") or f"WO #{idx+1}").strip()
        if item_name in existing_names:
            continue
            
        col_vals = {}
        for col_name in df.columns:
            if col_name == "Serial #": continue
            val = row.get(col_name)
            if pd.isna(val): continue
            col_id = col_map.get(col_name)
            if not col_id: continue
            if isinstance(val, (datetime, pd.Timestamp)):
                col_vals[col_id] = val.strftime("%Y-%m-%d")
            elif "Amount" in col_name or "Billed" in col_name or "Collected" in col_name or "Quantity" in col_name or "Balance" in col_name:
                try: col_vals[col_id] = str(float(val))
                except: col_vals[col_id] = str(val)
            else:
                col_vals[col_id] = str(val)
                
        gql(mutation, {"bId": WO_BOARD_ID, "name": item_name, "vals": json.dumps(col_vals)})
        count += 1
        if count % 25 == 0 or count == needed:
            print(f"  [Work Orders] Uploaded {count}/{needed}", flush=True)
        time.sleep(0.08)

if __name__ == "__main__":
    upload_deals()
    upload_work_orders()
    print("\nBoard seeding complete!", flush=True)
