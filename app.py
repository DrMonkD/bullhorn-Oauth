from flask import Flask, request, redirect, render_template_string, jsonify
import requests
import json
import os
import logging
import threading
import calendar
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CLIENT_ID = os.environ.get('BULLHORN_CLIENT_ID', 'b0c7f986-5620-490d-8364-2e943b3bbd2d')
CLIENT_SECRET = os.environ.get('BULLHORN_CLIENT_SECRET', 'j0I9c85nkGSPt6CTOaYnDAtw')
# Use localhost for local testing
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/oauth/callback')
TOKEN_FILE = 'token_store.json'
JOBS_FILE = 'jobs_store.json'

# Scheduler configuration
JOB_SYNC_INTERVAL = int(os.environ.get('JOB_SYNC_INTERVAL', 15))  # minutes
TOKEN_REFRESH_CHECK_INTERVAL = int(os.environ.get('TOKEN_REFRESH_CHECK_INTERVAL', 10))  # minutes

# Initialize scheduler
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()
logger.info("Background scheduler started")

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

def refresh_access_token(refresh_token):
    """Refresh the access token using refresh token - returns full token data"""
    try:
        token_url = 'https://auth.bullhornstaffing.com/oauth/token'
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        response = requests.post(token_url, params=params)
        data = response.json()
        
        if response.ok and 'access_token' in data:
            return {
                'access_token': data.get('access_token'),
                'refresh_token': data.get('refresh_token', refresh_token),  # Keep old if not provided
                'expires_in': data.get('expires_in', 3600),  # Default to 1 hour
                'rest_url': data.get('restUrl')  # May be included
            }
        return None
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        return None

def refresh_tokens_if_needed():
    """Proactively refresh access tokens if they're close to expiring"""
    tokens = load_tokens()
    if not tokens or not tokens.get('refresh_token'):
        return False
    
    # Check if we have expiration info
    expires_in = tokens.get('expires_in')
    saved_at = tokens.get('saved_at')
    
    if not expires_in or not saved_at:
        # Try to refresh anyway if we have refresh token
        logger.info("No expiration info, attempting token refresh")
        token_data = refresh_access_token(tokens.get('refresh_token'))
        if token_data:
            tokens['access_token'] = token_data['access_token']
            tokens['refresh_token'] = token_data.get('refresh_token', tokens.get('refresh_token'))
            tokens['expires_in'] = token_data.get('expires_in', 3600)
            if token_data.get('rest_url'):
                tokens['rest_url'] = token_data['rest_url']
            save_tokens(tokens)
            logger.info("Token refreshed successfully")
            return True
        return False
    
    # Calculate if token expires within 5 minutes
    try:
        saved_time = datetime.strptime(saved_at, '%Y-%m-%d %H:%M:%S')
        expires_at = saved_time + timedelta(seconds=int(expires_in))
        time_until_expiry = expires_at - datetime.now()
        
        if time_until_expiry.total_seconds() < 300:  # Less than 5 minutes
            logger.info(f"Token expires in {time_until_expiry}, refreshing...")
            token_data = refresh_access_token(tokens.get('refresh_token'))
            if token_data:
                tokens['access_token'] = token_data['access_token']
                tokens['refresh_token'] = token_data.get('refresh_token', tokens.get('refresh_token'))
                tokens['expires_in'] = token_data.get('expires_in', expires_in)
                if token_data.get('rest_url'):
                    tokens['rest_url'] = token_data['rest_url']
                save_tokens(tokens)
                logger.info("Token refreshed proactively")
                return True
    except Exception as e:
        logger.error(f"Error checking token expiration: {e}")
    
    return False

def get_bh_rest_token(force_refresh=False):
    """Get or create a valid BhRestToken session"""
    tokens = load_tokens()
    if not tokens or not tokens.get('access_token'):
        logger.warning("No tokens available for BhRestToken")
        return None, None
    
    # Check if we have a valid BhRestToken and it's not expired
    bh_rest_token = tokens.get('bh_rest_token')
    rest_url = tokens.get('rest_url')
    
    if bh_rest_token and not force_refresh:
        # Verify token is still valid by checking if we have rest_url
        if rest_url:
            return bh_rest_token, rest_url
    
    # Need to establish a new session
    access_token = tokens.get('access_token')
    if not rest_url:
        rest_url = 'https://rest.bullhornstaffing.com/rest-services/'
    elif not rest_url.startswith('http'):
        rest_url = 'https://' + rest_url
    if not rest_url.endswith('/'):
        rest_url += '/'
    
    login_urls = [f"{rest_url}login", 'https://rest.bullhornstaffing.com/rest-services/login']
    
    for login_url in login_urls:
        try:
            login_response = requests.post(
                login_url,
                params={'version': '*', 'access_token': access_token},
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            login_data = login_response.json()
            
            if login_response.ok and 'BhRestToken' in login_data:
                bh_rest_token = login_data['BhRestToken']
                if 'restUrl' in login_data:
                    rest_url = login_data['restUrl']
                    if not rest_url.endswith('/'):
                        rest_url += '/'
                
                # Save the session token
                tokens['bh_rest_token'] = bh_rest_token
                tokens['rest_url'] = rest_url
                save_tokens(tokens)
                logger.info("BhRestToken session established")
                return bh_rest_token, rest_url
        except Exception as e:
            logger.error(f"Error establishing session with {login_url}: {e}")
            continue
    
    # If still no token, try refreshing access token first
    if tokens.get('refresh_token'):
        logger.info("Attempting to refresh access token before establishing session")
        token_data = refresh_access_token(tokens.get('refresh_token'))
        if token_data:
            tokens['access_token'] = token_data['access_token']
            tokens['refresh_token'] = token_data.get('refresh_token', tokens.get('refresh_token'))
            tokens['expires_in'] = token_data.get('expires_in', tokens.get('expires_in', 3600))
            if token_data.get('rest_url'):
                tokens['rest_url'] = token_data['rest_url']
            save_tokens(tokens)
            # Retry with new token
            return get_bh_rest_token(force_refresh=True)
    
    logger.error("Failed to establish BhRestToken session")
    return None, None

def ensure_valid_session():
    """Ensure we have valid tokens and session - auto-refresh if needed"""
    # First, refresh tokens if needed
    refresh_tokens_if_needed()
    
    # Then, ensure we have a valid BhRestToken
    bh_rest_token, rest_url = get_bh_rest_token()
    return bh_rest_token, rest_url

def load_jobs():
    """Load jobs from file"""
    try:
        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading jobs: {e}")
    return {
        'last_sync': None,
        'bullhorn_jobs': [],
        'ahsa_jobs': [],
        'sync_stats': {
            'total_jobs': 0,
            'last_success': None,
            'last_error': None
        }
    }

def save_jobs(jobs_data):
    """Save jobs to file"""
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs_data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving jobs: {e}")
        return False

def fetch_bullhorn_jobs(rest_url, bh_rest_token):
    """Fetch jobs from Bullhorn API"""
    try:
        # Query Bullhorn for JobOrder entities
        # Adjust the query based on your needs
        query_url = f"{rest_url}query/JobOrder"
        
        # Basic query - you may want to customize this
        params = {
            'where': 'isOpen=1',  # Only open jobs
            'fields': 'id,title,dateAdded,dateLastModified,status,employmentType,address,clientContact',
            'orderBy': '-dateLastModified',
            'count': 500,  # Adjust as needed
            'BhRestToken': bh_rest_token
        }
        
        response = requests.get(query_url, params=params, timeout=30)
        
        if response.ok:
            data = response.json()
            jobs = data.get('data', [])
            logger.info(f"Fetched {len(jobs)} jobs from Bullhorn")
            return jobs
        else:
            logger.error(f"Failed to fetch jobs: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching Bullhorn jobs: {e}")
        return []

def sync_jobs_from_bullhorn():
    """Main function to sync jobs from Bullhorn - called by scheduler"""
    logger.info("Starting job sync from Bullhorn...")
    
    # Ensure we have a valid session
    bh_rest_token, rest_url = ensure_valid_session()
    
    if not bh_rest_token or not rest_url:
        logger.error("Cannot sync jobs: No valid session")
        jobs_data = load_jobs()
        jobs_data['sync_stats']['last_error'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_jobs(jobs_data)
        return False
    
    try:
        # Fetch jobs from Bullhorn
        bullhorn_jobs = fetch_bullhorn_jobs(rest_url, bh_rest_token)
        
        # Load existing jobs data
        jobs_data = load_jobs()
        
        # Update with new data
        jobs_data['bullhorn_jobs'] = bullhorn_jobs
        jobs_data['last_sync'] = datetime.now().isoformat()
        jobs_data['sync_stats']['total_jobs'] = len(bullhorn_jobs)
        jobs_data['sync_stats']['last_success'] = datetime.now().isoformat()
        jobs_data['sync_stats']['last_error'] = None
        
        save_jobs(jobs_data)
        logger.info(f"Successfully synced {len(bullhorn_jobs)} jobs from Bullhorn")
        return True
    except Exception as e:
        logger.error(f"Error during job sync: {e}")
        jobs_data = load_jobs()
        jobs_data['sync_stats']['last_error'] = datetime.now().isoformat()
        save_jobs(jobs_data)
        return False

def sync_jobs_from_ahsa():
    """Placeholder for future AHSA integration"""
    logger.info("AHSA sync not yet implemented")
    return False

@app.route('/keepalive')
def keepalive():
    """Keepalive endpoint - pinged by Render cron job to prevent shutdown"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'message': 'App is alive'
    }), 200

@app.route('/api/jobs')
def api_jobs():
    """API endpoint to get all synced jobs"""
    jobs_data = load_jobs()
    return jsonify(jobs_data)

@app.route('/api/jobs/sync', methods=['POST', 'GET'])
def api_jobs_sync():
    """Manually trigger job sync"""
    success = sync_jobs_from_bullhorn()
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Job sync completed successfully',
            'timestamp': datetime.now().isoformat()
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': 'Job sync failed - check logs',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/jobs/stats')
def api_jobs_stats():
    """Get job sync statistics"""
    jobs_data = load_jobs()
    return jsonify({
        'last_sync': jobs_data.get('last_sync'),
        'total_jobs': jobs_data.get('sync_stats', {}).get('total_jobs', 0),
        'bullhorn_jobs_count': len(jobs_data.get('bullhorn_jobs', [])),
        'ahsa_jobs_count': len(jobs_data.get('ahsa_jobs', [])),
        'last_success': jobs_data.get('sync_stats', {}).get('last_success'),
        'last_error': jobs_data.get('sync_stats', {}).get('last_error')
    })


@app.route('/api/submissions')
def api_submissions():
    """Fetch job submissions from Bullhorn with candidate, status, job title, client.
    GET /api/submissions?year=YYYY&month=M
    """
    bh_rest_token, rest_url = ensure_valid_session()
    if not bh_rest_token or not rest_url:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"

    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    fields = 'id,dateAdded,status,source,candidate(id,firstName,lastName,email),jobOrder(id,title,clientCorporation(id,name))'

    if not rest_url.endswith('/'):
        rest_url += '/'
    url = f"{rest_url}query/JobSubmission"

    all_data = []
    start = 0
    count = 500
    while True:
        params = {
            'BhRestToken': bh_rest_token,
            'where': f"dateAdded>={start_ms} AND dateAdded<={end_ms}",
            'fields': fields,
            'orderBy': '-dateAdded',
            'count': count,
            'start': start
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

        records = data.get('data', [])
        if not records:
            break
        all_data.extend(records)
        if len(records) < count:
            break
        start += count

    return jsonify({
        'success': True,
        'count': len(all_data),
        'year': year,
        'month': month,
        'data': all_data
    })


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
            # Get REST URL from login endpoint
            access_token = data.get('access_token')
            rest_url = data.get('restUrl')
            
            # If restUrl not in initial response, we need to call /login to get it
            if not rest_url:
                try:
                    # Try to get REST URL from the login endpoint
                    login_url = 'https://rest.bullhornstaffing.com/rest-services/login'
                    login_response = requests.post(
                        login_url,
                        params={'access_token': access_token, 'version': '*'},
                        headers={'Content-Type': 'application/x-www-form-urlencoded'}
                    )
                    login_data = login_response.json()
                    if login_response.ok and 'restUrl' in login_data:
                        rest_url = login_data['restUrl']
                except Exception as e:
                    print(f"Error getting REST URL: {e}")
            
            # Save tokens
            tokens = {
                'access_token': access_token,
                'refresh_token': data.get('refresh_token'),
                'rest_url': rest_url,
                'expires_in': data.get('expires_in')
            }
            save_tokens(tokens)
            
            if rest_url:
                return render_template_string(HTML_TEMPLATE, 
                    tokens=tokens, 
                    message="✅ OAuth success – tokens saved to token_store.json")
            else:
                return render_template_string(HTML_TEMPLATE, 
                    tokens=tokens, 
                    message="⚠️ Tokens saved but REST URL not available. You may need to contact Bullhorn support.")
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
    """Test API connection - uses auto-login"""
    tokens = load_tokens()
    
    if not tokens or not tokens.get('access_token'):
        return render_template_string(HTML_TEMPLATE, 
            error=True, 
            message="No tokens found. Please authenticate first.")
    
    try:
        # Use auto-login to ensure valid session
        bh_rest_token, rest_url = ensure_valid_session()
        
        if not bh_rest_token or not rest_url:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                error=True, 
                message="Failed to establish session. Please try re-authenticating.")
        
        # Test with the BhRestToken (try as header first, then as param)
        ping_url = f"{rest_url}ping"
        response = requests.get(
            ping_url,
            headers={'BhRestToken': bh_rest_token}
        )
        
        # If header approach fails, try as query parameter
        if not response.ok:
            response = requests.get(
                ping_url,
                params={'BhRestToken': bh_rest_token}
            )
        
        data = response.json()
        
        if response.ok:
            expires = datetime.fromtimestamp(data['sessionExpires']/1000).strftime('%Y-%m-%d %H:%M:%S')
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                message=f"✅ Connection successful! Session expires: {expires}")
        else:
            return render_template_string(HTML_TEMPLATE, 
                tokens=tokens, 
                error=True, 
                message=f"API test failed: {data}")
    
    except Exception as e:
        logger.error(f"Error in test route: {e}")
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

# Schedule background jobs
def schedule_background_jobs():
    """Schedule periodic background tasks"""
    # Schedule token refresh check
    scheduler.add_job(
        func=refresh_tokens_if_needed,
        trigger=IntervalTrigger(minutes=TOKEN_REFRESH_CHECK_INTERVAL),
        id='token_refresh',
        name='Refresh tokens if needed',
        replace_existing=True
    )
    logger.info(f"Scheduled token refresh check every {TOKEN_REFRESH_CHECK_INTERVAL} minutes")
    
    # Schedule job sync from Bullhorn
    scheduler.add_job(
        func=sync_jobs_from_bullhorn,
        trigger=IntervalTrigger(minutes=JOB_SYNC_INTERVAL),
        id='job_sync_bullhorn',
        name='Sync jobs from Bullhorn',
        replace_existing=True
    )
    logger.info(f"Scheduled job sync every {JOB_SYNC_INTERVAL} minutes")

if __name__ == '__main__':
    # Schedule background jobs
    schedule_background_jobs()
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
