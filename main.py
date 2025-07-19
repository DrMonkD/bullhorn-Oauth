from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import traceback
import os
import json

app = Flask(__name__)
CORS(app)

# Load from environment variables (set these in Render)
CLIENT_ID = os.getenv("BULLHORN_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.getenv("BULLHORN_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://www.concordphysicians.com/oauth/callback")

token_url = 'https://auth.bullhornstaffing.com/oauth/token'
rest_login_url = 'https://rest.bullhornstaffing.com/rest-services/login?version=2.0&access_token='


@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Bullhorn OAuth Test</title></head>
    <body>
      <h2>Exchange Bullhorn OAuth Code</h2>
      <input type="text" id="code" placeholder="Paste OAuth code here" size="60">
      <button onclick="sendCode()">Submit</button>
      <pre id="result"></pre>

      <script>
        function getCodeFromURL() {
          const params = new URLSearchParams(window.location.search);
          return params.get('code');
        }

        async function sendCode() {
          const code = document.getElementById("code").value.trim();
          const result = document.getElementById("result");
          result.textContent = "Sending...";

          try {
            const response = await fetch("/exchange", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ code })
            });

            const data = await response.json();
            result.textContent = JSON.stringify(data, null, 2);
          } catch (err) {
            result.textContent = "Error: " + err;
          }
        }

        window.onload = function () {
          const code = getCodeFromURL();
          if (code) {
            document.getElementById("code").value = code;
            sendCode();
          }
        }
      </script>
    </body>
    </html>
    '''


@app.route('/exchange', methods=['POST'])
def exchange_code():
    data = request.json
    code = data.get('code')
    if not code:
        return jsonify({'error': 'Missing code'}), 400

    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI
    }

    token_resp = requests.post(token_url, data=payload)
    if token_resp.status_code != 200:
        return jsonify({'error': 'Token request failed', 'details': token_resp.text}), 500

    token_data = token_resp.json()
    access_token = token_data.get('access_token')

    login_resp = requests.get(rest_login_url + access_token)
    if login_resp.status_code != 200:
        return jsonify({'error': 'Login failed', 'details': login_resp.text}), 500

    login_data = login_resp.json()

    # Save tokens to tokens.json
    with open("tokens.json", "w") as f:
        json.dump({
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "BhRestToken": login_data.get("BhRestToken"),
            "restUrl": login_data.get("restUrl")
        }, f)

    return jsonify({
        'access_token': access_token,
        'BhRestToken': login_data.get('BhRestToken'),
        'restUrl': login_data.get('restUrl')
    })


@app.route('/show-jobs')
def show_jobs():
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)

        bh_token = tokens["BhRestToken"]
        rest_url = tokens["restUrl"]

        url = f"{rest_url}search/JobOrder?query=isOpen:1&fields=id,title,dateAdded,employmentType,clientCorporation(name)&sort=-dateAdded&count=10&BhRestToken={bh_token}"
        resp = requests.get(url)
        jobs = resp.json().get("data", [])

        html = "<h2>Latest Bullhorn Jobs</h2><ul>"
        for job in jobs:
            html += f"<li><b>{job['title']}</b> — {job['clientCorporation']['name']}<br><i>{job['employmentType']}</i> | {job['dateAdded']}</li><br>"
        html += "</ul>"

        return html
    except Exception:
        return f"<pre>Error:\n{traceback.format_exc()}</pre>", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
