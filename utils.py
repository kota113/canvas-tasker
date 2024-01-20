import requests
import time
import envs


def validate_token(refresh_token: str, access_token: str, expiry: int = None):
    if access_token is None and expiry is None:
        raise ValueError("Either access_token or expiry must be specified.")
    if expiry:
        if time.time() > expiry - 60:
            access_token, expiry = fetch_new_token(refresh_token)
            return access_token, expiry
    else:
        url = "https://www.googleapis.com/oauth2/v3/tokeninfo"
        params = {"access_token": access_token}
        r = requests.get(url, params=params)
        if r.status_code != 200 or r.json()["expires_in"] < 60:
            access_token, expiry = fetch_new_token(refresh_token)
    return access_token, expiry


def fetch_new_token(refresh_token: str):
    url = "https://oauth2.googleapis.com/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    body = {
        "client_id": envs.OAUTH2_CLIENT_ID,
        "client_secret": envs.OAUTH2_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    r = requests.post(url, headers=headers, data=body)
    r.raise_for_status()
    access_token = r.json()["access_token"]
    expiry = time.time() + r.json()["expires_in"]
    return access_token, expiry
