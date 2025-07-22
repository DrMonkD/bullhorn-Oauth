from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import traceback
import os
import json
from auth_utils import get_bullhorn_session

app = Flask(__name__)
CORS(app)

# Load from environment variables (set these in Render)
CLIENT_ID = os.getenv("BULLHORN_CLIENT_ID", "YOUR_CLIENT_ID")
CLIENT_SECRET = os.getenv("BULLHORN_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://bullhorn-oauth-app.onrender.com/oauth/callback")

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


@app.route('/oauth/callback')
def oauth_callback():
    return '''
    <script>
      async function sendCode() {
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code");
        if (!code) return;

        const result = await fetch("/exchange", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code })
        });

        const data = await result.json();
        console.log("Exchange response:", data);
        document.body.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
      }

      window.onload = sendCode;
    </script>
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
        session = get_bullhorn_session()
        bh_token = session["BhRestToken"]
        rest_url = session["restUrl"]

        jobs_url = f"{rest_url}search/JobOrder?query=isOpen:1&fields=*&count=20&BhRestToken={bh_token}"
        resp = requests.get(jobs_url)

        return f"<pre>{resp.text}</pre>"
    except Exception as e:
        return f"<pre>Error:\n{traceback.format_exc()}</pre>", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
