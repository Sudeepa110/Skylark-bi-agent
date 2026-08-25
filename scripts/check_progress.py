import os, urllib.request, json
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("MONDAY_TOKEN", "")
workspace_id = int(os.getenv("WORKSPACE_ID", "3364949"))
headers = {'Authorization': token, 'Content-Type': 'application/json'}

def check():
    if not token:
        print("Please configure MONDAY_TOKEN in .env")
        return
    query = f'{{ boards (workspace_ids: [{workspace_id}]) {{ id name items_page (limit: 500) {{ items {{ id name }} }} }} }}'
    req = urllib.request.Request('https://api.monday.com/v2', data=json.dumps({'query': query}).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        for b in res.get('data', {}).get('boards', []):
            print(f"Board: '{b['name']}' (ID: {b['id']}) - Total Items: {len(b.get('items_page', {}).get('items', []))}")

if __name__ == '__main__':
    check()
