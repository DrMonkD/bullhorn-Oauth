from flask import Flask, request, jsonify, send_file
import requests
import traceback
import json
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CLIENT_ID = 'b0c7f986-5620-490d-8364-2e943b3bbd2d'
CLIENT_SECRET = 'j0I9c85nkGSPt6CTOaYnDAtw'
REDIRECT_URI = 'https://www.concordphysicians.com/oauth/callback'

TOKEN_URL = 'https://auth.bullhornstaffing.com/oauth/token'
LOGIN_URL = 'https://rest.bullhornstaffing.com/rest-services/login'

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
            const response = await fetch("/callback", {
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

@app.route('/callback', methods=['GET', 'POST'])
def callback():
    if request.method == 'POST':
        code = request.json.get('code')
    else:
        code = request.args.get('code')

    if not code:
        return jsonify({'error': 'No code provided'}), 400

    token_payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI
    }

    token_resp = requests.post(TOKEN_URL, data=token_payload)
    if token_resp.status_code != 200:
        return jsonify({'error': 'Token exchange failed', 'details': token_resp.text}), 500

    token_data = token_resp.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')

    login_resp = requests.get(f"{LOGIN_URL}?version=*&access_token={access_token}")
    if login_resp.status_code != 200:
        return jsonify({'error': 'REST login failed', 'details': login_resp.text}), 500

    login_data = login_resp.json()
    bhrest_token = login_data.get('BhRestToken')
    rest_url = login_data.get('restUrl')

    # Save tokens to local file
    with open("tokens.json", "w") as f:
        json.dump({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "BhRestToken": bhrest_token,
            "restUrl": rest_url
        }, f)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "BhRestToken": bhrest_token,
        "restUrl": rest_url
    })

@app.route('/download-tokens')
def download_tokens():
    if not os.path.exists("tokens.json"):
        return jsonify({'error': 'tokens.json not found'}), 404
    return send_file("tokens.json", as_attachment=True)

@app.route('/job-board')
def job_board():
    bh_token = "26754_7939010_b8a584da-0f4d-494b-85cc-2dd459a4719c"
    rest_url = "https://rest44.bullhornstaffing.com/rest-services/bu5kp0/"

    try:
        jobs_url = f"{rest_url}search/JobOrder?query=isOpen:1&fields=id,title,publicDescription,dateAdded&count=10&BhRestToken={bh_token}"
        resp = requests.get(jobs_url)
        data = resp.json()

        if not data or 'data' not in data:
            raise ValueError("No job data returned")

        jobs = data['data']
        html = "<h2>Open Job Listings</h2><ul>"
        for job in jobs:
            title = job.get('title', 'Untitled')
            description = job.get('publicDescription') or ''
            html += f"<li><strong>{title}</strong><br>{description[:200]}...</li><br>"
        html += "</ul>"
        return html
    except Exception:
        return f"<pre>{traceback.format_exc()}</pre>", 500

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
    except Exception as e:
        return f"<pre>Error:\n{traceback.format_exc()}</pre>", 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
