import requests, os, json
from config import *

def refresh_bullhorn_token(refresh_token):
    res = requests.post("https://auth.bullhornstaffing.com/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": BULLHORN_CLIENT_ID,
        "client_secret": BULLHORN_CLIENT_SECRET
    })

    if res.status_code != 200:
        raise Exception(f"Refresh failed: {res.text}")

    new_tokens = res.json()

    settings = requests.get("https://rest.bullhornstaffing.com/rest-services/login", params={
        "version": "*",
        "access_token": new_tokens["access_token"]
    }).json()

    new_tokens["BhRestToken"] = settings["BhRestToken"]
    new_tokens["restUrl"] = settings["restUrl"]

    with open("token_store.json", "w") as f:
        json.dump(new_tokens, f)

    return new_tokens
