import requests
import json

CLIENT_ID = 'b0c7f986-5620-490d-8364-2e943b3bbd2d'
CLIENT_SECRET = 'j0I9c85nkGSPt6CTOaYnDAtw'
TOKEN_URL = 'https://auth.bullhornstaffing.com/oauth/token'
LOGIN_URL = 'https://rest.bullhornstaffing.com/rest-services/login'

def get_bullhorn_session():
    with open('tokens.json', 'r') as f:
        tokens = json.load(f)

    refresh_token = tokens['refresh_token']
    refresh_response = requests.post(TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    })

    if refresh_response.status_code != 200:
        raise Exception("Failed to refresh access token")

    refresh_data = refresh_response.json()
    access_token = refresh_data['access_token']
    new_refresh_token = refresh_data.get('refresh_token', refresh_token)

    login_response = requests.get(f"{LOGIN_URL}?version=*&access_token={access_token}")
    login_data = login_response.json()

    bhrest_token = login_data['BhRestToken']
    rest_url = login_data['restUrl']

    with open('tokens.json', 'w') as f:
        json.dump({
            "refresh_token": new_refresh_token,
            "access_token": access_token,
            "BhRestToken": bhrest_token,
            "restUrl": rest_url
        }, f)

    return {
        "BhRestToken": bhrest_token,
        "restUrl": rest_url
    }
