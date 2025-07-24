from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

CLIENT_ID = "b0c7f986-5620-490d-8364-2e943b3bbd2d"
CLIENT_SECRET = "j0I9c85nkGSPt6CTOaYnDAtw"
REDIRECT_URI = "https://bullhorn-oauth.onrender.com/oauth/callback"
TOKEN_FILE = "token.json"

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
        return "❌ Authorization code not found", 400

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    response = requests.post("https://auth.bullhornstaffing.com/oauth/token", data=payload)
    if response.status_code != 200:
        return f"❌ Token exchange failed: {response.status_code} - {response.text}", 500

    token_data = response.json()
    access_token = token_data.get("access_token")

    login_params = {
        "version": "*",
        "access_token": access_token
    }
    login_response = requests.get("https://rest.bullhornstaffing.com/rest-services/login", params=login_params)

    if login_response.status_code != 200:
        return f"❌ Login failed: {login_response.status_code} - {login_response.text}", 500

    login_data = login_response.json()
    bhrest_token = login_data.get("BhRestToken")
    rest_url = login_data.get("restUrl")

    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": access_token,
            "BhRestToken": bhrest_token,
            "restUrl": rest_url
        }, f)

    return login_data

@app.route("/me")
def get_user():
    global access_token, bhrest_token, rest_url

    if not os.path.exists(TOKEN_FILE):
        return "❌ No token found. Please authenticate first.", 400

    with open(TOKEN_FILE, "r") as f:
        data = json.load(f)

    bhrest_token = data["BhRestToken"]
    rest_url = data["restUrl"]

    headers = {
        "BhRestToken": bhrest_token
    }

    # ✅ Correct endpoint
    response = requests.get(f"{rest_url}find/CorporateUser/ME", headers=headers)
    if response.status_code != 200:
        return f"❌ Failed to retrieve user info: {response.status_code} - {response.text}", 500

    return response.json()



if __name__ == "__main__":
    app.run()
