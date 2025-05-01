from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import traceback

app = Flask(__name__)
CORS(app)  # Allow all origins (safe for testing only)

CLIENT_ID = 'b0c7f986-5620-490d-8364-2e943b3bbd2d'
CLIENT_SECRET = 'j0I9c85nkGSPt6CTOaYnDAtw'
REDIRECT_URI = 'https://www.concordphysicians.com/oauth/callback'

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

    return jsonify({
        'access_token': access_token,
        'BhRestToken': login_data.get('BhRestToken'),
        'restUrl': login_data.get('restUrl')
    })

@app.route('/jobs', methods=['POST'])
def get_jobs():
    data = request.json
    bh_token = data.get('BhRestToken')
    rest_url = data.get('restUrl')

    if not bh_token or not rest_url:
        return jsonify({'error': 'Missing BhRestToken or restUrl'}), 400

    try:
        jobs_url = f"{rest_url}search/JobOrder?query=isOpen:1&fields=id,title,publicDescription,dateAdded&count=10&BhRestToken={bh_token}"
        resp = requests.get(jobs_url)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            html += f"<li><strong>{job.get('title')}</strong><br>{job.get('publicDescription', '')[:200]}...</li><br>"
        html += "</ul>"
        return html
    except Exception:
        return f"<pre>{traceback.format_exc()}</pre>", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
