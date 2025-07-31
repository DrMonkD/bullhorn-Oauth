import json
import requests

# Load the token store
def load_tokens():
    with open("token_store.json", "r") as f:
        return json.load(f)

# Fetch open jobs from Bullhorn
def fetch_bullhorn_jobs(bh_rest_token, rest_url):
    url = f"{rest_url}search/JobOrder"
    params = {
        "query": "isOpen:1",  # only open jobs
        "fields": "id,title,dateAdded,publicDescription",
        "BhRestToken": bh_rest_token,
        "count": 100  # adjust as needed
    }
    res = requests.get(url, params=params)
    
    if res.status_code != 200:
        raise Exception(f"Failed to fetch jobs: {res.text}")

    return res.json().get("data", [])

if __name__ == "__main__":
    tokens = load_tokens()
    bh_rest_token = tokens["bh_rest_token"]
    rest_url = tokens["rest_url"]

    jobs = fetch_bullhorn_jobs(bh_rest_token, rest_url)
    
    print(f"✅ Pulled {len(jobs)} jobs from Bullhorn:\n")
    for job in jobs:
        print(f"- {job['title']} (ID: {job['id']})")
