from flask import Flask, redirect, request
import os
import requests
import json
from urllib.parse import quote
  
app = Flask(__name__)

# Read secrets from environment
CLIENT_ID = os.environ.get("BULLHORN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BULLHORN_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("BULLHORN_REDIRECT_URI")

@app.route("/")
def start_auth():
    # Debug: Print environment variables
    print(f"CLIENT_ID: {CLIENT_ID}")
    print(f"CLIENT_SECRET: {'*' * len(CLIENT_SECRET) if CLIENT_SECRET else 'None'}")
    print(f"REDIRECT_URI: {REDIRECT_URI}")
    
    # Check if any are None
    if not CLIENT_ID or not CLIENT_SECRET:
        return f"❌ Missing environment variables! CLIENT_ID: {CLIENT_ID}, CLIENT_SECRET: {'Set' if CLIENT_SECRET else 'Missing'}", 500
    
    # Try WITHOUT redirect_uri parameter first to test
    auth_url = f"https://auth.bullhornstaffing.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code"
    print(f"Authorization URL (without redirect_uri): {auth_url}")
    
    return redirect(auth_url)

@app.route("/oauth/callback")
def callback():
    code = request.args.get("code")

    # Step 1: Exchange code for access token (without redirect_uri)
    token_response = requests.post("https://auth.bullhornstaffing.com/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })

    # Debug: Print the response
    print(f"Token Response Status: {token_response.status_code}")
    print(f"Token Response Body: {token_response.text}")

    token_data = token_response.json()
    
    # Check if there's an error
    if "error" in token_data:
        return f"❌ OAuth Error: {token_data.get('error')} - {token_data.get('error_description', 'No description')}", 400
    
    # Check if access_token exists
    if "access_token" not in token_data:
        return f"❌ Token exchange failed. Response: {token_data}", 400

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
