from flask import Flask, request
import requests

app = Flask(__name__)

CLIENT_ID = "b0c7f986-5620-490d-8364-2e943b3bbd2d"
CLIENT_SECRET = "j0I9c85nkGSPt6CTOaYnDAtw"
REDIRECT_URI = "https://bullhorn-oauth-app.onrender.com/oauth/callback"
API_USERNAME = "concordphysician.api"

@app.route("/")
def home():
    return "Bullhorn OAuth App is running."

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return "Authorization code not found", 400

    # Exchange code for access token
    token_url = "https://auth.bullhornstaffing.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI
    }

    token_response = requests.post(token_url, data=payload)
    if token_response.status_code != 200:
        return f"Token request failed: {token_response.text}", 500

    token_data = token_response.json()
    access_token = token_data.get("access_token")

    # Optional: Authenticate to get BH Rest token
    login_url = "https://rest.bullhornstaffing.com/rest-services/login"
    login_params = {
        "version": "*",
        "access_token": access_token
    }

    login_response = requests.get(login_url, params=login_params)
    if login_response.status_code != 200:
        return f"Login failed: {login_response.text}", 500

    login_data = login_response.json()
    return f"""
    <h3>Success!</h3>
    <p><b>Access Token:</b> {access_token}</p>
    <p><b>BhRestToken:</b> {login_data.get('BhRestToken')}</p>
    <p><b>REST URL:</b> {login_data.get('restUrl')}</p>
    """

if __name__ == "__main__":
    app.run(debug=True)
