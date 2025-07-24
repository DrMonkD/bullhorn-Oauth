from flask import Flask, redirect, request
import requests
import os
import json

from config import *

app = Flask(__name__)

@app.route("/")
def home():
    auth_url = f"https://auth.bullhornstaffing.com/oauth/authorize?client_id={BULLHORN_CLIENT_ID}&response_type=code&redirect_uri={BULLHORN_REDIRECT_URI}"
    return redirect(auth_url)

@app.route("/oauth/callback")
def callback():
    code = request.args.get('code')
    token_res = requests.post("https://auth.bullhornstaffing.com/oauth/token", data={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': BULLHORN_CLIENT_ID,
        'client_secret': BULLHORN_CLIENT_SECRET,
        'redirect_uri': BULLHORN_REDIRECT_URI
    }).json()

    refresh_token = token_res.get("refresh_token")
    access_token = token_res.get("access_token")

    settings = requests.get("https://rest.bullhornstaffing.com/rest-services/login", params={
        "version": "*",
        "access_token": access_token
    }).json()

    token_data = {
        "refresh_token": refresh_token,
        "access_token": access_token,
        "restUrl": settings["restUrl"],
        "BhRestToken": settings["BhRestToken"]
    }

    with open("token_store.json", "w") as f:
        json.dump(token_data, f)

    return "Token stored! You can now start syncing."

if __name__ == "__main__":
    app.run(debug=True)
