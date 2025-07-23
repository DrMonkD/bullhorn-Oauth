from flask import Flask, request
import requests

app = Flask(__name__)

# Bullhorn client credentials
CLIENT_ID = "b0c7f986-5620-490d-8364-2e943b3bbd2d"
CLIENT_SECRET = "j0I9c85nkGSPt6CTOaYnDAtw"
REDIRECT_URI = "https://bullhorn-oauth.onrender.com/oauth/callback"

# Global storage (for demo; replace with persistent storage in production)
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

    # Exchange code for access token
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

    # Immediately refresh BhRestToken
    refresh_response = refresh_bhrest_token()
    if isinstance(refresh_response, tuple):  # error response
        return refresh_response

    return {
        "access_token": access_token,
        "BhRestToken": bhrest_token,
        "restUrl": rest_url
    }

def refresh_bhrest_token():
    global access_token, bhrest_token, rest_url

    if not access_token:
        return {"error": "Missing access token. Please reauthorize."}, 401

    login_url = "https://rest.bullhornstaffing.com/rest-services/login"
    params = {
        "version": "*",
        "access_token": access_token
    }

    response = requests.get(login_url, params=params)
    if response.status_code != 200:
        return {"error": "Failed to refresh BhRestToken", "details": response.text}, 500

    data = response.json()
    bhrest_token = data.get("BhRestToken")
    rest_url = data.get("restUrl")
    return data

@app.route("/me")
def get_user():
    refresh_result = refresh_bhrest_token()
    if isinstance(refresh_result, tuple):  # error response
        return refresh_result

    headers = {
        "BhRestToken": bhrest_token
    }

    user_response = requests.get(f"{rest_url}/user/ME", headers=headers)
    if user_response.status_code != 200:
        return f"Failed to retrieve user info: {user_response.status_code} - {user_response.text}", 500

    return user_response.json()

if __name__ == "__main__":
    app.run()
