from flask import Flask, request, redirect, render_template_string, jsonify
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
CLIENT_ID = os.environ.get('BULLHORN_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('BULLHORN_CLIENT_SECRET', '')
REDIRECT_URI = 'https://bullhorn-oauth.onrender.com/oauth/callback'
TOKEN_FILE = 'token_store.json'

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bullhorn OAuth</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen p-6">
    <div class="max-w-4xl mx-auto">
        <div class="bg-white rounded-lg shadow-xl p-8">
            <div class="flex items-center gap-3 mb-6">
                <svg class="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                </svg>
                <h1 class="text-3xl font-bold text-gray-800">Bullhorn OAuth</h1>
            </div>

            {% if message %}
            <div class="mb-4 p-4 {% if error %}bg-red-50 border-red-200{% else %}bg-green-50 border-green-200{% endif %} border rounded-lg">
                <p class="{% if error %}text-red-800{% else %}text-green-800{% endif %}">{{ message }}</p>
            </div>
            {% endif %}

            {% if tokens %}
            <div class="mb-6 p-6 bg-green-50 border border-green-200 rounded-lg">
                <h3 class="text-lg font-semibold text-green-800 mb-3">✅ OAuth Success</h3>
                <div class="space-y-3 text-sm">
                    <div>
                        <span class="font-medium text-gray-700">Access Token:</span>
                        <p class="text-gray-600 break-all font-mono text-xs mt-1">{{ tokens.access_token }}</p>
                    </div>
                    {% if tokens.refresh_token %}
                    <div>
                        <span class="font-medium text-gray-700">Refresh Token:</span>
                        <p class="text-gray-600 break-all font-mono text-xs mt-1">{{ tokens.refresh_token }}</p>
                    </div>
                    {% endif %}
                    <div>
                        <span class="font-medium text-gray-700">REST URL:</span>
                        <p class="text-gray-600 break-all font-mono text-xs mt-1">{{ tokens.rest_url if tokens.rest_url else 'Not available - please re-authenticate' }}</p>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">Saved:</span>
                        <p class="text-gray-600 text-xs mt-1">{{ tokens.saved_at }}</p>
                    </div>
                </div>
            </div>

            <div class="flex gap-3 mb-6">
                <a href="/test" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                    Test Connection
                </a>
                <a href="/logout" class="px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
                    Clear Tokens
                </a>
            </div>
            {% else %}
            <div class="mb-6">
                <p class="text-gray-700 mb-4">Click the button below to authenticate with Bullhorn.</p>
                <a href="/login" class="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                    </svg>
                    Start OAuth Flow
                </a>
            </div>
            {% endif %}

            <div class="mt-8 p-6 bg-gray-50 rounded-lg">
                <h3 class="text-lg font-semibold text-gray-800 mb-3">How It Works</h3>
                <ol class="list-decimal list-inside space-y-2 text-gray-700">
                    <li>Click "Start OAuth Flow" to authenticate with Bullhorn</li>
                    <li>Login with your Bullhorn credentials</li>
                    <li>You'll be redirected back with tokens automatically saved</li>
                    <li>Use "Test Connection" to verify the API connection</li>
                    <li>Tokens are saved to <code class="bg-gray-200 px-1 rounded">token_store.json</code></li>
                </ol>
            </div>
        </div>
    </div>
</body>
</html>
'''

def load_tokens():
    """Load tokens from file"""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading tokens: {e}")
    return None

def save_tokens(tokens):
    """Save tokens to file"""
    try:
        tokens['saved_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving tokens: {e}")
        return False

@app.route('/')
def home():
    """Home page - show status"""
    tokens = load_tokens()
    return render_template_string(HTML_TEMPLATE, tokens=tokens)

@app.route('/login')
def login():
    """Redirect to Bullhorn OAuth"""
    if not CLIENT_ID:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="CLIENT_ID not configured. Set environment variable BULLHORN_CLIENT_ID")
    
    auth_url = f"https://auth.bullhornstaffing.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}"
    return redirect(auth_url)

@app.route('/oauth/callback')
def callback():
    """Handle OAuth callback"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message=f"OAuth error: {error}")
    
    if not code:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="No authorization code received")
    
    # Exchange code for token
    try:
        token_url = 'https://auth.bullhornstaffing.com/oauth/token'
        params = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI
        }
        
        response = requests.post(token_url, params=params)
        data = response.json()
        
        if response.ok and 'access_token' in data:
            # Save tokens
            tokens = {
                'access_token': data.get('access_token'),
                'refresh_token': data.get('refresh_token'),
                'rest_url': data.get('restUrl'),
                'expires_in': data.get('expires_in')
            }
            save_tokens(tokens)
            
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                message="✅ OAuth success – tokens saved to token_store.json")
        else:
            return render_template_string(HTML_TEMPLATE, 
                error=True, 
                message=f"Token exchange failed: {data.get('error_description', data)}")
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message=f"Error: {str(e)}")

@app.route('/test')
def test():
    """Test API connection"""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('access_token'):
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="No tokens found. Please authenticate first.")
    
    try:
        rest_url = tokens.get('rest_url')
        access_token = tokens.get('access_token')
        
        if not rest_url:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                error=True, 
                message="REST URL not found in tokens. Please re-authenticate.")
        
        # Ensure rest_url has proper format
        if not rest_url.startswith('http'):
            rest_url = 'https://' + rest_url
        
        # Ensure rest_url ends with /
        if not rest_url.endswith('/'):
            rest_url += '/'
        
        response = requests.get(
            f"{rest_url}ping",
            headers={'BhRestToken': access_token}
        )
        data = response.json()
        
        if response.ok:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                message=f"✅ Connection successful! Session expires: {datetime.fromtimestamp(data['sessionExpires']/1000).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                error=True, 
                message=f"API test failed: {data}")
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
            tokens=tokens, 
            error=True, 
            message=f"Error: {str(e)}")

@app.route('/logout')
def logout():
    """Clear tokens"""
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        return render_template_string(HTML_TEMPLATE, 
            message="Tokens cleared successfully")
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message=f"Error clearing tokens: {str(e)}")

@app.route('/api/tokens')
def api_tokens():
    """API endpoint to get current tokens"""
    tokens = load_tokens()
    if tokens:
        return jsonify(tokens)
    return jsonify({'error': 'No tokens found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
