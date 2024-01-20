import random
import string
import time
import urllib.parse

import dataset
import requests
from flask import Flask, url_for, request, redirect, session, render_template
from google.auth.transport import requests as grequests
from google.oauth2 import id_token

import envs
import utils

app = Flask(__name__)
app.secret_key = envs.SESSION_SECRET
db = dataset.connect("mysql://prod@100.65.209.33/prod", engine_kwargs={"pool_recycle": 3600})
users_table = db["users"]


@app.route('/')
def index():
    if "user_id" in session:
        session["access_token"], session["expiry"] = \
            utils.validate_token(
                session["refresh_token"],
                session["expiry"],
                session["access_token"]
            )
    return render_template("index.html")


@app.route('/tos')
def tos():
    return render_template("tos.html")


@app.route('/privacy-policy')
def privacy_policy():
    return render_template("privacy-policy.html")


@app.route('/oauth2')
def oauth2():
    # google oauth2 request
    base_url = "https://accounts.google.com/o/oauth2/v2/auth?"
    state = generate_state()
    session["state"] = state
    params = {
        "scope": "https://www.googleapis.com/auth/tasks openid",
        # "scope": "https://www.googleapis.com/auth/tasks",
        "access_type": "offline",
        # "prompt": "consent",
        "response_type": "code",
        "state": state,
        "redirect_uri": url_for("callback", _scheme="https", _external=True),
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
    user_info = decode_id_token(r.json()["id_token"])
    if user_info is None:
        return {"error": "Invalid request."}, 401
    session["user_id"] = user_info["sub"]
    session["access_token"] = r.json()["access_token"]
    expiry = time.time() + r.json()["expires_in"]
    session["expiry"] = expiry
    if "refresh_token" in r.json():
        refresh_token = r.json()["refresh_token"]
        users_table.upsert(dict(
            user_id=user_info["sub"],
            access_token=r.json()["access_token"],
            refresh_token=refresh_token,
            expiry=expiry
        ), ["user_id"])
    else:
        users_table.upsert(dict(
            user_id=user_info["sub"],
            access_token=r.json()["access_token"],
            expiry=expiry
        ), ["user_id"])
    return redirect(url_for("index"))


@app.route('/api/tasklists', methods=["GET"])
def get_user_tasklists():
    if "access_token" not in session:
        return {"error": "Forbidden"}, 403
    url = "https://tasks.googleapis.com/tasks/v1/users/@me/lists"
    params = {"access_token": session["access_token"]}
    r = requests.get(url, params=params)
    if "items" not in r.json():
        return {"error": "Invalid request."}, 401
    tasklists: list = []
    if users_table.find_one(user_id=session["user_id"])["tasklist_id"] is None:
        tasklists: list = [{"title": "SOL 課題 (リストを新規作成)", "id": "createNewList"}]
    tasklists.extend(r.json()["items"])
    return tasklists


@app.route('/api/set-ical-url', methods=["POST"])
def set_ical_url():
    if "access_token" not in session:
        return {"error": "Forbidden"}, 403
    if "icalUrl" not in request.get_json():
        return {"error": "Forbidden"}, 403
    ical_url = request.get_json()["icalUrl"]
    users_table.update({"user_id": session["user_id"], "ical_url": ical_url}, ["user_id"])
    return {"result": "OK"}, 200


@app.route('/api/set-tasklist', methods=["POST"])
def set_tasklist():
    if "access_token" not in session:
        return {"error": "Invalid request."}, 403
    if "tasklist" not in request.get_json():
        return {"error": "Invalid request."}, 400
    tasklist_id = request.get_json()["tasklist"]
    if tasklist_id == "createNewList":
        url = "https://tasks.googleapis.com/tasks/v1/users/@me/lists"
        params = {"access_token": session["access_token"]}
        r = requests.post(url, params=params, json={"title": "SOL 課題"})
        tasklist_id = r.json()["id"]
    users_table.update({"user_id": session["user_id"], "tasklist_id": tasklist_id}, ["user_id"])
    return {"result": "OK"}, 200


# decode google open id token
def decode_id_token(token: str):
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        id_info = id_token.verify_oauth2_token(token, grequests.Request(), envs.OAUTH2_CLIENT_ID)
        # ID token is valid. Get the user's Google Account ID from the decoded token.
        return id_info
    except ValueError:
        # Invalid token
        return None


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("index"))


# logout on error
@app.errorhandler(500)
def logout_on_error(e):
    session.clear()
    return redirect(url_for("index"))


def generate_state():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


if __name__ == '__main__':
    app.run()
