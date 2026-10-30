"""CopeeMachine backend: Google sign-in, then private Keep-style notes per user (MongoDB),
synced live across that user's devices."""
import base64
import json
import os
import queue
import re
import secrets
import smtplib
import ssl
import threading
import time
from collections import defaultdict
from email.message import EmailMessage
from html import escape
from pathlib import Path

import requests as http
from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request, session
from google.auth.transport import requests as grequests
from google.oauth2 import id_token
from pymongo import DESCENDING, MongoClient
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

ROOT = Path(__file__).resolve().parent  # the backend folder is self-contained
load_dotenv(ROOT / ".env")

PRODUCTION = os.environ.get("APP_ENV") == "production"
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
DEV_LOGIN = os.environ.get("COPEE_DEV_LOGIN") == "1"  # local testing only, never in production
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MAX_TEXT = 200_000
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1" if PRODUCTION else "0") == "1"
if PRODUCTION and DEV_LOGIN:
    raise SystemExit("COPEE_DEV_LOGIN must not be enabled when APP_ENV=production")
if PRODUCTION and not COOKIE_SECURE:
    raise SystemExit("COOKIE_SECURE must be 1 when APP_ENV=production (serve over HTTPS)")
# The frontend is hosted separately. List its origin(s) here, comma-separated, e.g. https://notes.example.com
CORS_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()}
# "None" is needed when the frontend and API are on different sites (e.g. two *.onrender.com hosts);
# "Lax" works when they share a registrable domain (app.example.com + api.example.com).
SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")
if SAMESITE not in ("Lax", "None", "Strict"):
    raise SystemExit("COOKIE_SAMESITE must be Lax, None or Strict")
if SAMESITE == "None" and not COOKIE_SECURE:
    raise SystemExit("COOKIE_SAMESITE=None requires COOKIE_SECURE=1 (HTTPS)")
if not CLIENT_ID and not DEV_LOGIN:
    raise SystemExit("Set GOOGLE_CLIENT_ID in .env — see README for how to get one")
if not MONGODB_URI:
    raise SystemExit("Set MONGODB_URI in .env")

DATA = Path(os.environ.get("DATA_DIR") or ROOT / "data")
DATA.mkdir(parents=True, exist_ok=True)

_key = DATA / "secret"
if not _key.exists():
    _key.write_text(secrets.token_hex(32))
    _key.chmod(0o600)

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("SECRET_KEY") or _key.read_text()
if os.environ.get("TRUST_PROXY") == "1":  # behind nginx/Render/Fly etc: trust one hop of X-Forwarded-*
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    MAX_CONTENT_LENGTH=1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=SAMESITE,
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=30 * 24 * 3600,
)

mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
db = mongo[os.environ.get("MONGODB_DB", "copeemachine")]
users, notes, settings = db.users, db.notes, db.settings
notes.create_index([("user", 1), ("pinned", DESCENDING), ("updated", DESCENDING)])

# ---------- live sync (per user) ----------
clients: dict[str, set] = defaultdict(set)


def broadcast(user, event, data):
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    for q in list(clients[user]):
        q.put(msg)


def note_json(n, reveal=False):
    """A locked note's body never leaves the server unless the passcode was just entered for it."""
    locked = bool(n.get("locked"))
    return {"id": n["_id"], "title": n["title"], "body": "" if locked and not reveal else n["body"],
            "color": n["color"], "pinned": n["pinned"], "locked": locked,
            "createdAt": n["created"], "updatedAt": n["updated"]}


# The API only returns JSON, so it needs no scripts, frames or images of its own.
CSP = "default-src 'none'; frame-ancestors 'none'"


@app.get("/healthz")
def healthz():
    try:
        mongo.admin.command("ping")
    except Exception:
        return jsonify(ok=False), 503
    return jsonify(ok=True, email=email_method())


@app.after_request
def headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin and origin in CORS_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        resp.headers["Access-Control-Max-Age"] = "600"
        resp.headers.add("Vary", "Origin")
    if PRODUCTION:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        resp.headers["Content-Security-Policy"] = CSP
    return resp


PUBLIC = {"/api/config", "/api/me", "/api/auth/google", "/api/auth/dev"}


@app.before_request
def guard():
    p = request.path
    if request.method == "OPTIONS" or not p.startswith("/api/") or p in PUBLIC:
        return  # CORS preflights carry no cookie; the real request is checked below
    if "user" not in session:
        return jsonify(error="Not logged in"), 401
    origin = request.headers.get("Origin")
    if (request.method != "GET" and origin and origin.rstrip("/") not in CORS_ORIGINS
            and origin.split("://", 1)[-1] != request.host):
        return jsonify(error="Bad origin"), 403


# ---------- auth ----------
def sign_in(sub, email, name, picture, verified=False):
    users.update_one({"_id": sub}, {"$set": {"email": email, "name": name, "picture": picture,
                                              "verified": verified}}, upsert=True)
    session.clear()
    session["user"] = sub
    session.permanent = True
    return jsonify(user={"email": email, "name": name, "picture": picture})


@app.get("/api/config")
def config():
    return jsonify(clientId=CLIENT_ID, dev=DEV_LOGIN)


@app.post("/api/auth/google")
def auth_google():
    cred = (request.get_json(silent=True) or {}).get("credential")
    try:
        info = id_token.verify_oauth2_token(cred, grequests.Request(), CLIENT_ID)
    except Exception:
        return jsonify(error="Google sign-in failed"), 401
    if not info.get("email_verified"):
        return jsonify(error="Email not verified"), 401
    return sign_in(info["sub"], info["email"], info.get("name", ""), info.get("picture", ""), verified=True)


@app.post("/api/auth/dev")
def auth_dev():
    if not DEV_LOGIN:
        abort(404)
    who = (request.get_json(silent=True) or {}).get("name") or "dev"
    return sign_in(f"dev:{who}", f"{who}@example.test", who, "")


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    if "user" not in session:
        return jsonify(user=None)
    u = users.find_one({"_id": session["user"]}, {"_id": 0, "email": 1, "name": 1, "picture": 1})
    return jsonify(user=u)


# ---------- notes ----------
COLORS = {"default", "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink", "gray"}


@app.get("/api/notes")
def list_notes():
    rows = notes.find({"user": session["user"]}).sort([("pinned", DESCENDING), ("updated", DESCENDING)])
    return jsonify([note_json(n) for n in rows])


@app.post("/api/notes")
def create_note():
    d = request.get_json(silent=True) or {}
    now = int(time.time() * 1000)
    color = d.get("color", "default")
    n = {"_id": secrets.token_urlsafe(9), "user": session["user"],
         "title": str(d.get("title", ""))[:500], "body": str(d.get("body", ""))[:MAX_TEXT],
         "color": color if color in COLORS else "default", "pinned": bool(d.get("pinned")),
         "created": now, "updated": now}
    notes.insert_one(n)
    broadcast(session["user"], "note", note_json(n))
    return jsonify(note_json(n)), 201


# ---------- locked notes ----------
# One passcode, stored hashed in the `settings` collection (set it with scripts/set_passcode.py).
# Entering it for a note opens that note for this session until it is closed again.
UNLOCK_LIMIT, UNLOCK_WINDOW = 5, 300  # wrong passcodes per user per 5 minutes
unlock_fails: dict[str, list] = defaultdict(list)


def is_open(nid):
    return nid in session.get("open", [])


@app.post("/api/notes/<nid>/unlock")
def unlock_note(nid):
    user, now = session["user"], time.time()
    fails = unlock_fails[user] = [t for t in unlock_fails[user] if now - t < UNLOCK_WINDOW]
    if len(fails) >= UNLOCK_LIMIT:
        return jsonify(error="Too many wrong passcodes, try again in a few minutes"), 429
    n = notes.find_one({"_id": nid, "user": user})
    if not n:
        abort(404)
    stored = settings.find_one({"_id": "passcode"}) or {}
    code = str((request.get_json(silent=True) or {}).get("passcode", ""))
    if not stored.get("hash"):
        return jsonify(error="No passcode is set on the server"), 503
    if not check_password_hash(stored["hash"], code):
        fails.append(now)
        return jsonify(error="Wrong passcode"), 403
    session["open"] = [x for x in session.get("open", []) if x != nid][-49:] + [nid]
    return jsonify(note_json(n, reveal=True))


@app.post("/api/notes/<nid>/close")
def close_note(nid):
    session["open"] = [x for x in session.get("open", []) if x != nid]
    return jsonify(ok=True)


@app.patch("/api/notes/<nid>")
def update_note(nid):
    d = request.get_json(silent=True) or {}
    sets = {}
    n = notes.find_one({"_id": nid, "user": session["user"]}, {"locked": 1})
    if not n:
        abort(404)
    # Reading or changing a locked note's text, or removing its lock, needs the passcode first.
    if n.get("locked") and ("title" in d or "body" in d or d.get("locked") is False) and not is_open(nid):
        return jsonify(error="This note is locked"), 403
    if "locked" in d: sets["locked"] = bool(d["locked"])
    if d.get("locked") is True and d.get("keepOpen"):  # locked from the open editor: stay editable until closed
        session["open"] = [x for x in session.get("open", []) if x != nid][-49:] + [nid]
    if "title" in d: sets["title"] = str(d["title"])[:500]
    if "body" in d: sets["body"] = str(d["body"])[:MAX_TEXT]
    if d.get("color") in COLORS: sets["color"] = d["color"]
    if "pinned" in d: sets["pinned"] = bool(d["pinned"])
    sets["updated"] = int(time.time() * 1000)
    n = notes.find_one_and_update({"_id": nid, "user": session["user"]}, {"$set": sets}, return_document=True)
    if not n:
        abort(404)
    broadcast(session["user"], "note", note_json(n))
    return jsonify(note_json(n, reveal=is_open(nid)))


@app.delete("/api/notes/<nid>")
def delete_note(nid):
    if not notes.delete_one({"_id": nid, "user": session["user"]}).deleted_count:
        abort(404)
    broadcast(session["user"], "gone", {"id": nid})
    return jsonify(ok=True)


# ---------- email a note ----------
# Two ways to send. Gmail API (HTTPS, works where SMTP ports are blocked, e.g. Render's free tier) is used
# when GMAIL_REFRESH_TOKEN is set; otherwise SMTP. Both send FROM the owner's account TO the signed-in user.
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()  # .strip(): pasted values often carry a stray space/newline
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN", "").strip()
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "").strip()  # the Gmail account that authorized the refresh token
USE_GMAIL_API = bool(GMAIL_REFRESH_TOKEN and GOOGLE_CLIENT_SECRET and CLIENT_ID and GMAIL_SENDER)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER
EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
EMAIL_LIMIT, EMAIL_WINDOW = 20, 3600  # per user per hour
sent_log: dict[str, list] = defaultdict(list)


def email_method():
    return "gmail-api" if USE_GMAIL_API else "smtp" if (SMTP_HOST and SMTP_FROM) else "none"


_gmail_token = {"value": "", "expires": 0.0}
_gmail_lock = threading.Lock()


class EmailError(Exception):
    """Carries a message that is safe to show the user."""


def gmail_access_token():
    """Short-lived access token minted from the stored refresh token, cached until shortly before expiry."""
    with _gmail_lock:
        if _gmail_token["value"] and time.time() < _gmail_token["expires"] - 60:
            return _gmail_token["value"]
        r = http.post("https://oauth2.googleapis.com/token", timeout=15, data={
            "client_id": CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GMAIL_REFRESH_TOKEN, "grant_type": "refresh_token"})
        if r.status_code != 200:
            app.logger.error("gmail token refresh failed %s: %s", r.status_code, r.text[:200])
            if "invalid_grant" in r.text:
                raise EmailError("Email authorization expired, the server owner must re-run gmail_authorize.py")
            try:
                reason = r.json().get("error", "")  # Google's code, e.g. invalid_client; never a secret
            except ValueError:
                reason = ""
            raise EmailError("Couldn't authorize with Gmail" + (f" ({reason})" if reason else ""))
        d = r.json()
        _gmail_token.update(value=d["access_token"], expires=time.time() + int(d.get("expires_in", 3600)))
        return _gmail_token["value"]


def send_via_gmail_api(msg):
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = http.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", timeout=15,
                  headers={"Authorization": f"Bearer {gmail_access_token()}"}, json={"raw": raw})
    if r.status_code == 401:  # token revoked mid-cache: drop it so the next try mints a new one
        _gmail_token["value"] = ""
    if r.status_code >= 400:
        app.logger.error("gmail send failed %s: %s", r.status_code, r.text[:300])
        raise EmailError("Gmail refused to send the email")


def send_via_smtp(msg):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
        s.starttls(context=ssl.create_default_context())
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)


@app.post("/api/notes/<nid>/email")
def email_note(nid):
    if not (USE_GMAIL_API or (SMTP_HOST and SMTP_FROM)):
        return jsonify(error="Email isn't set up on the server (see GMAIL_* or SMTP_* in .env)"), 503
    me = users.find_one({"_id": session["user"]}, {"email": 1, "name": 1, "verified": 1}) or {}
    to = me.get("email", "")  # always the signed-in user's own Google address, never taken from the request
    if not me.get("verified") or len(to) > 254 or not EMAIL_RE.match(to):
        return jsonify(error="Sign in with Google to email notes to yourself"), 400
    n = notes.find_one({"_id": nid, "user": session["user"]})
    if not n:
        abort(404)
    if n.get("locked") and not is_open(nid):
        return jsonify(error="This note is locked"), 403
    now = time.time()
    log = sent_log[session["user"]] = [t for t in sent_log[session["user"]] if now - t < EMAIL_WINDOW]
    if len(log) >= EMAIL_LIMIT:
        return jsonify(error="Too many emails sent, try again later"), 429

    msg = EmailMessage()
    msg["Subject"] = " ".join((n["title"] or "Note").split())[:200]
    msg["From"] = f"{me.get('name') or 'CopeeMachine'} via CopeeMachine <{GMAIL_SENDER if USE_GMAIL_API else SMTP_FROM}>"
    msg["To"] = to
    title, body = n["title"].strip(), n["body"]
    msg.set_content("\n\n".join(x for x in (title, body, "Sent by CopeeMachine") if x))
    html_title = f"<b>{escape(title)}</b>" if title else ""
    msg.add_alternative(
        f'<div style="white-space:pre-wrap">{html_title}{"<br><br>" if title and body else ""}{escape(body)}<br><br>Sent by CopeeMachine</div>',
        subtype="html")
    try:
        (send_via_gmail_api if USE_GMAIL_API else send_via_smtp)(msg)
    except EmailError as e:
        return jsonify(error=str(e)), 502
    except Exception as e:
        app.logger.error("email send failed: %s: %s", type(e).__name__, e)
        return jsonify(error="Couldn't send the email, check the server's email settings"), 502
    log.append(now)
    return jsonify(ok=True)


@app.get("/api/events")
def events():
    user, q = session["user"], queue.Queue()
    clients[user].add(q)

    def stream():
        try:
            yield "retry: 2000\n\n"
            while True:
                try:
                    yield q.get(timeout=25)
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            clients[user].discard(q)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- root ----------
@app.get("/")
def root():
    return jsonify(service="copeemachine-api", ok=True)


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="Not found"), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), threaded=True)
