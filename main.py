
from flask import Flask, redirect, request, session, jsonify, send_file
import requests
import json
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

CLIENT_ID = 'b0c7f986-5620-490d-8364-2e943b3bbd2d'
CLIENT_SECRET = 'j0I9c85nkGSPt6CTOaYnDAtw'
REDIRECT_URI = 'https://www.concordphysicians.com/oauth/callback'

AUTH_URL = 'https://auth.bullhornstaffing.com/oauth/authorize'
TOKEN_URL = 'https://auth.bullhornstaffing.com/oauth/token'
LOGIN_URL = 'https://rest.bullhornstaffing.com/rest-services/login'

@app.route('/')
def index():
    return '<a href="/login">Login with Bullhorn</a>'

@app.route('/login')
def login():
    return redirect(f"{AUTH_URL}?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "No code provided", 400

    response = requests.post(TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI
    })
    data = response.json()
    access_token = data['access_token']
    refresh_token = data['refresh_token']

    rest_response = requests.get(f"{LOGIN_URL}?version=*&access_token={access_token}")
    rest_data = rest_response.json()

    with open("tokens.json", "w") as f:
        json.dump({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "BhRestToken": rest_data['BhRestToken'],
            "restUrl": rest_data['restUrl']
        }, f)

    return "✅ tokens.json has been saved."

@app.route('/download-tokens')
def download_tokens():
    return send_file("tokens.json", as_attachment=True)

@app.route('/debug-tokens')
def debug_tokens():
    try:
        with open("tokens.json") as f:
            return f"<pre>{f.read()}</pre>"
    except Exception as e:
        return str(e), 500


if __name__ == '__main__':
    app.run(debug=True)
