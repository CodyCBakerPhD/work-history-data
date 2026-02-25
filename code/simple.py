import requests
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
GITHUB_USERNAME = "codycbakerphd"
TOKEN = os.getenv("GITHUB_TOKEN")
DATE = "2026-01-01"

# Convert DATE into a 24-hour window
start = datetime.fromisoformat(DATE)
end = start + timedelta(days=30)

start_iso = start.isoformat()
end_iso = end.isoformat()

# GitHub Search API endpoint
url = "https://api.github.com/search/issues"

# Query: issues authored by you, created within the date window
query = f"author:{GITHUB_USERNAME} type:issue created:{start_iso}..{end_iso}"

response = requests.get(
    url,
    headers={"Bearer": f"token {TOKEN}"},
    params={"q": query}
)

data = response.json()

print(f"Found {data.get('total_count', 0)} issues:")
for item in data.get("items", []):
    print(f"- {item['title']} ({item['html_url']})")
