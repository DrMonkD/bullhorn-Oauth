import os
import json
import requests
 
# Load from token_store.json
def load_tokens():
    with open("token_store.json", "r") as f:
        return json.load(f)

# Save to token_store.json
def save_tokens(tokens):
    with open("token_store.json", "w") as f:
        json.dump(tokens, f, indent=2)

# Refresh access token using the stored refresh_token
def refresh_tokens():
    tokens = load_tokens()

    refresh_token = tokens["refresh_token"]
    client_id = os.environ["BULLHORN_CLIENT_ID"]
    client_secret = os.environ["BULLHORN_CLIENT_SECRET"]

    res = requests.post("https://auth.bullhornstaffing.com/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret
    })

    if res.status_code != 200:
        raise Exception(f"Token refresh failed: {res.text}")

    new_token_data = res.json()
    tokens.update(new_token_data)

    # Get BhRestToken and restUrl again
    access_token = new_token_data["access_token"]
    login_res = requests.get("https://rest.bullhornstaffing.com/rest-services/login", params={
        "version": "*",
        "access_token": access_token
    })

    login_data = login_res.json()
    tokens["bh_rest_token"] = login_data["BhRestToken"]
    tokens["rest_url"] = login_data["restUrl"]

    save_tokens(tokens)
    return tokens
