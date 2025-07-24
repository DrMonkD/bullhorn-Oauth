import json
import requests
from slugify import slugify
from refresh_bullhorn_token import refresh_bullhorn_token
from config import *

try:
    with open("token_store.json") as f:
        tokens = json.load(f)
except:
    raise Exception("Run the /oauth/callback to initialize tokens first.")

tokens = refresh_bullhorn_token(tokens["refresh_token"])
bh_token = tokens["BhRestToken"]
rest_url = tokens["restUrl"]

def get_bullhorn_jobs():
    res = requests.get(f"{rest_url}search/JobOrder", params={
        "query": "isOpen:1",
        "fields": "id,title,publicDescription,dateAdded",
        "BhRestToken": bh_token,
        "count": 500
    }).json()
    return res.get("data", [])

def get_webflow_jobs():
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_KEY}",
        "accept-version": "1.0.0"
    }
    res = requests.get(
        f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items?limit=100",
        headers=headers
    )
    return res.json().get("items", [])

def sync_jobs():
    bh_jobs = get_bullhorn_jobs()
    wf_jobs = get_webflow_jobs()

    wf_map = {item['name']: item for item in wf_jobs}
    bh_ids = set()

    for job in bh_jobs:
        title = job["title"]
        slug = slugify(title)
        bh_ids.add(title)

        data = {
            "fields": {
                "name": title,
                "slug": slug,
                "description": job.get("publicDescription", ""),
                "_archived": False,
                "_draft": False
            }
        }

        headers = {
            "Authorization": f"Bearer {WEBFLOW_API_KEY}",
            "accept-version": "1.0.0",
            "Content-Type": "application/json"
        }

        if title in wf_map:
            job_id = wf_map[title]["_id"]
            requests.patch(
                f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items/{job_id}",
                headers=headers,
                json=data
            )
        else:
            requests.post(
                f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items",
                headers=headers,
                json=data
            )

    for title, item in wf_map.items():
        if title not in bh_ids:
            job_id = item["_id"]
            requests.delete(
                f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items/{job_id}",
                headers={
                    "Authorization": f"Bearer {WEBFLOW_API_KEY}",
                    "accept-version": "1.0.0"
                }
            )

if __name__ == "__main__":
    sync_jobs()
