import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY5NjU3Mzc3OCwiYWFpIjoxMSwidWlkIjoxMTQzMTQwMjQsImlhZCI6IjIwMjYtMDgtMjVUMDQ6NDM6MjIuNzA1WiIsInBlciI6Im1lOndyaXRlIiwiYWN0aWQiOjM2NjAyNDM4LCJyZ24iOiJhcHNlMiJ9.kCU2-yUe1z-zGZEACelKjhGL51gZXrMGCzIbOeFF5Kc'
headers = {'Authorization': token, 'Content-Type': 'application/json'}

def check():
    query = '{ boards (workspace_ids: [3364949]) { id name items_page (limit: 500) { items { id name } } } }'
    req = urllib.request.Request('https://api.monday.com/v2', data=json.dumps({'query': query}).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        for b in res['data']['boards']:
            print(f"Board: '{b['name']}' (ID: {b['id']}) - Total Items: {len(b.get('items_page', {}).get('items', []))}")

if __name__ == '__main__':
    check()
