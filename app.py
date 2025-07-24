from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# Bullhorn OAuth credentials
CLIENT_ID = "b0c7f986-5620-490d-8364-2e943b3bbd2d"
CLIENT_SECRET = "j0I9c85nkGSPt6CTOaYnDAtw"
REDIRECT_URI = "https://bullhorn-oauth.onrender.com/oauth/callback"
TOKEN_FILE = "token.json"

# Runtime globals
access_token = None
bhrest_token = None
rest_url = None

@app.route("/")
def home():
    return "✅ Bullhorn OAuth Flask App is Running"

@app.route("/oauth/callback")
def oauth_callback():
    global access_token, bhrest_token, rest_url

    code = request.args.get("code")
    if not code:
        print("❌ No authorization code in callback request")
        return "❌ Authorization code not found", 400

    print(f"🔁 Received authorization code: {code}")

    token_url = "https://auth.bullhornstaffing.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    try:
        response = requests.post(token_url, data=payload)
        print("🔁 Token exchange response:", response.status_code, response.text)
    except Exception as e:
        print("❌ Exception during token exchange:", e)
        return f"❌ Token exchange failed: {e}", 500

    if response.status_code != 200:
        return f"❌ Token exchange failed: {response.status_code} - {response.text}", 500

    token_data = response.json()
    access_token = token_data.get("access_token")
    print("✅ Access token obtained:", access_token)

    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": access_token}, f)
        print("💾 Token saved to file")
    except Exception as e:
        print("❌ Failed to save token file:", e)

    refresh_result = refresh_bhrest_token()
    if isinstance(refresh_result, tuple):  # error
        return refresh_result

    return {
        "access_token": access_token,
        "BhRestToken": bhrest_token,
        "restUrl": rest_url
    }

def refresh_bhrest_token():
    global access_token, bhrest_token, rest_url

    if not access_token:
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    data = json.load(f)
                    access_token = data.get("access_token")
                    print("📂 Loaded access_token from file:", access_token)
            except Exception as e:
                print("❌ Failed to read token file:", e)
                return "❌ Failed to read token file", 500
        else:
            return "❌ No access_token available", 400

    login_url = "https://rest.bullhornstaffing.com/rest-services/login"
    login_params = {
        "version": "*",
        "access_token": access_token
    }

    try:
        login_response = requests.get(login_url, params=login_params)
        print("🔐 Login response:", login_response.status_code, login_response.text)
    except Exception as e:
        print("❌ Exception during login:", e)
        return "❌ Exception during login", 500

    if login_response.status_code != 200:
        return f"❌ Failed to refresh BhRestToken: {login_response.status_code} - {login_response.text}", 500

    login_data = login_response.json()
    bhrest_token = login_data.get("BhRestToken")
    rest_url = login_data.get("restUrl")

    print("✅ Refreshed BhRestToken:", bhrest_token)
    print("✅ REST URL:", rest_url)

    return "✅ Token refreshed"

@app.route("/me")
def get_user():
    refresh_result = refresh_bhrest_token()
    if isinstance(refresh_result, tuple):  # error response
        return refresh_result

    headers = {
        "BhRestToken": bhrest_token
    }

    user_response = requests.get(f"{rest_url}/user/ME", headers=headers)
    print("👤 /user/ME response:", user_response.status_code, user_response.text)

    if user_response.status_code != 200:
        return f"❌ Failed to retrieve user info: {user_response.status_code} - {user_response.text}", 500

    return user_response.json()

if __name__ == "__main__":
    app.run()
