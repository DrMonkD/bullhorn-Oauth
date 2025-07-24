from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# Bullhorn client credentials
CLIENT_ID = "b0c7f986-5620-490d-8364-2e943b3bbd2d"
CLIENT_SECRET = "j0I9c85nkGSPt6CTOaYnDAtw"
REDIRECT_URI = "https://bullhorn-oauth.onrender.com/oauth/callback"

# Global runtime vars
access_token = None
bhrest_token = None
rest_url = None
TOKEN_FILE = "tokens.json"

@app.route("/")
def home():
    return "✅ Bullhorn OAuth Flask App is Running"

@app.route("/oauth/callback")
def oauth_callback():
    global access_token, bhrest_token, rest_url

    code = request.args.get("code")
    if not code:
        return "❌ Authorization code not found", 400

    token_url = "https://auth.bullhornstaffing.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        return f"❌ Token exchange failed: {response.status_code} - {response.text}", 500

    token_data = response.json()
    access_token = token_data.get("access_token")

    # Save to disk
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": access_token}, f)

    refresh_result = refresh_bhrest_token()
    if isinstance(refresh_result, tuple):
        return refresh_result

    return {
        "access_token": access_token,
        "BhRestToken": bhrest_token,
        "restUrl": rest_url
    }

def refresh_bhrest_token():
    global access_token, bhrest_token, rest_url

    # Load access_token if needed
    if not access_token:
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    access_token = data.get("access_token")
            except Exception as e:
                return {"error": "Failed to read token file", "details": str(e)}, 500
        else:
            return {"error": "Missing access token. Please reauthorize."}, 401

    login_url = "https://rest.bullhornstaffing.com/rest-services/login"
    params = {
        "version": "*",
        "access_token": access_token
    }

    response = requests.get(login_url, params=params)
    if response.status_code != 200:
        return {
            "error": "Failed to refresh BhRestToken",
            "details": response.text
        }, 500

    data = response.json()
    bhrest_token = data.get("BhRestToken")
    rest_url = data.get("restUrl")
    return data

@app.route("/me")
def get_user():
    global access_token, bhrest_token, rest_url

    refresh_result = refresh_bhrest_token()
    if isinstance(refresh_result, tuple):
        return refresh_result

    if not bhrest_token or not rest_url:
        return "❌ Missing BhRestToken or restUrl", 400

    headers = {
        "BhRestToken": bhrest_token
    }

print("Loaded access_token from file:", access_token)

    try:
        user_response = requests.get(f"{rest_url}/user/ME", headers=headers)
        user_response.raise_for_status()
        return user_response.json()
    except Exception as e:
        return f"❌ Failed to retrieve user info: {e}", 500

if __name__ == "__main__":
    app.run()
