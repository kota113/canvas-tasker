import random
import string

import requests
from flask import Flask, url_for, request, redirect, session
import urllib.parse
import envs

app = Flask(__name__)
app.secret_key = envs.SESSION_SECRET


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/oauth2')
def oauth2():
    # google oauth2 request
    base_url = "https://accounts.google.com/o/oauth2/v2/auth?"
    state = generate_state()
    session["state"] = state
    params = {
        "scope": "https://www.googleapis.com/auth/tasks",
        "access_type": "offline",
        "include_granted_scopes": "true",
        "response_type": "code",
        "state": state,
        "redirect_uri": url_for("callback", _scheme="https", _external=True),
        # "redirect_uri": "http://localhost:5000/callback",
        "client_id": envs.OAUTH2_CLIENT_ID
    }
    url = base_url + urllib.parse.urlencode(params)
    return redirect(url)


@app.route('/callback')
def callback():
    args = request.args
    url = "https://oauth2.googleapis.com/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    params = dict(
        code=args["code"],
        client_id=envs.OAUTH2_CLIENT_ID,
        client_secret=envs.OAUTH2_CLIENT_SECRET,
        grant_type="authorization_code",
        redirect_uri=url_for("callback", _scheme="https", _external=True)
    )
    r = requests.post(url, data=params, headers=headers)
    with open("oauth2_token.json", "w") as f:
        f.write(r.text)
    return True


def generate_state():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


if __name__ == '__main__':
    app.run()
