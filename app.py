from flask import Flask, redirect, request
import os
import requests
import json
from urllib.parse import urlencode
  
app = Flask(__name__)

# Read secrets from environment
CLIENT_ID = os.environ.get("BULLHORN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BULLHORN_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("BULLHORN_REDIRECT_URI")

@app.route("/")
def start_auth():
    # Debug logging
    print(f"CLIENT_ID: {CLIENT_ID}")
    print(f"CLIENT_SECRET: {'SET' if CLIENT_SECRET else 'NOT SET'}")
    print(f"REDIRECT_URI: {REDIRECT_URI}")
    
    # Check if environment variables are set
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        return f"ERROR: Missing environment variables!<br>CLIENT_ID: {CLIENT_ID}<br>REDIRECT_URI: {REDIRECT_URI}<br>CLIENT_SECRET: {'SET' if CLIENT_SECRET else 'NOT SET'}", 500
    
    # Build the authorization URL with proper URL encoding
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI
    }
    auth_url = f"https://auth.bullhornstaffing.com/oauth/authorize?{urlencode(params)}"
    print(f"Redirecting to: {auth_url}")
    
    return redirect(auth_url)

@app.route("/oauth/callback")
def callback():
    code = request.args.get("code")
    
    print(f"Received callback with code: {code}")

    # Step 1: Exchange code for access token
    token_response = requests.post("https://auth.bullhornstaffing.com/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI
    })

    print(f"Token response status: {token_response.status_code}")
    print(f"Token response body: {token_response.text}")

    token_data = token_response.json()
    
    # Check for errors
    if "error" in token_data:
        return f"ERROR: {token_data.get('error')} - {token_data.get('error_description', 'No description')}", 400
    
    if "access_token" not in token_data:
        return f"ERROR: No access_token in response. Response: {token_data}", 400

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
