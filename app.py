from flask import Flask, redirect, request
import os
import requests
import json
  
app = Flask(__name__)

# Read secrets from environment
CLIENT_ID = os.environ.get("BULLHORN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BULLHORN_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("BULLHORN_REDIRECT_URI")

@app.route("/")
def start_auth():
    print(f"DEBUG - CLIENT_ID: {CLIENT_ID}")
    print(f"DEBUG - REDIRECT_URI: {REDIRECT_URI}")
    
    if not REDIRECT_URI:
        return "ERROR: BULLHORN_REDIRECT_URI environment variable is not set!", 500
    
    auth_url = f"https://auth.bullhornstaffing.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    print(f"DEBUG - Auth URL: {auth_url}")
    
    return redirect(auth_url)

@app.route("/oauth/callback")
def callback():
    code = request.args.get("code")

    # Step 1: Exchange code for access token
    token_response = requests.post("https://auth.bullhornstaffing.com/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI
    })

    token_data = token_response.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # Step 2: Get BhRestToken and restUrl
    settings_response = requests.get("https://rest.bullhornstaffing.com/rest-services/login", params={
        "version": "*",
        "access_token": access_token
    })

    settings_data = settings_response.json()
    bh_rest_token = settings_data["BhRestToken"]
    rest_url = settings_data["restUrl"]

    # Step 3: Save everything
    with open("token_store.json", "w") as f:
        json.dump({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "bh_rest_token": bh_rest_token,
            "rest_url": rest_url
        }, f, indent=2)

    return "✅ OAuth success – tokens saved to token_store.json"

if __name__ == "__main__":
    app.run(debug=True)
