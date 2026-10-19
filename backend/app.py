"""CopeeMachine backend: Google sign-in, then private Keep-style notes per user (MongoDB),
synced live across that user's devices."""
import json
import os
import queue
import re
import secrets
import smtplib
import ssl
import time
from collections import defaultdict
from email.message import EmailMessage
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request, send_from_directory, session
from google.auth.transport import requests as grequests
from google.oauth2 import id_token
from pymongo import DESCENDING, MongoClient
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PRODUCTION = os.environ.get("APP_ENV") == "production"
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
DEV_LOGIN = os.environ.get("COPEE_DEV_LOGIN") == "1"  # local testing only, never in production
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MAX_TEXT = 200_000
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1" if PRODUCTION else "0") == "1"
if PRODUCTION and DEV_LOGIN:
    raise SystemExit("COPEE_DEV_LOGIN must not be enabled when APP_ENV=production")
if PRODUCTION and not COOKIE_SECURE:
    raise SystemExit("COOKIE_SECURE must be 1 when APP_ENV=production (serve over HTTPS)")
if not CLIENT_ID and not DEV_LOGIN:
    raise SystemExit("Set GOOGLE_CLIENT_ID in .env — see README for how to get one")
if not MONGODB_URI:
    raise SystemExit("Set MONGODB_URI in .env")

DATA = ROOT / "data"
DIST = ROOT / "frontend" / "dist"
DATA.mkdir(exist_ok=True)

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
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=30 * 24 * 3600,
)

mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
db = mongo[os.environ.get("MONGODB_DB", "copeemachine")]
users, notes = db.users, db.notes
notes.create_index([("user", 1), ("pinned", DESCENDING), ("updated", DESCENDING)])

# ---------- live sync (per user) ----------
clients: dict[str, set] = defaultdict(set)


def broadcast(user, event, data):
    msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    for q in list(clients[user]):
        q.put(msg)


def note_json(n):
    return {"id": n["_id"], "title": n["title"], "body": n["body"], "color": n["color"],
            "pinned": n["pinned"], "createdAt": n["created"], "updatedAt": n["updated"]}


# Allows Google Identity Services (sign-in button + popup) and nothing else off-site.
CSP = ("default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; "
       "frame-src https://accounts.google.com/gsi/; connect-src 'self' https://accounts.google.com/gsi/; "
       "style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; "
       "img-src 'self' data: https:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")


@app.get("/healthz")
def healthz():
    try:
        mongo.admin.command("ping")
    except Exception:
        return jsonify(ok=False), 503
    return jsonify(ok=True)


@app.after_request
def headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    # Google sign-in popup needs window.opener access.
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    if PRODUCTION:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        resp.headers["Content-Security-Policy"] = CSP
    return resp


PUBLIC = {"/api/config", "/api/me", "/api/auth/google", "/api/auth/dev"}


@app.before_request
def guard():
    p = request.path
    if not p.startswith("/api/") or p in PUBLIC:
        return
    if "user" not in session:
        return jsonify(error="Not logged in"), 401
    origin = request.headers.get("Origin")
    if request.method != "GET" and origin and origin.split("://", 1)[-1] != request.host:
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


@app.patch("/api/notes/<nid>")
def update_note(nid):
    d = request.get_json(silent=True) or {}
    sets = {}
    if "title" in d: sets["title"] = str(d["title"])[:500]
    if "body" in d: sets["body"] = str(d["body"])[:MAX_TEXT]
    if d.get("color") in COLORS: sets["color"] = d["color"]
    if "pinned" in d: sets["pinned"] = bool(d["pinned"])
    sets["updated"] = int(time.time() * 1000)
    n = notes.find_one_and_update({"_id": nid, "user": session["user"]}, {"$set": sets}, return_document=True)
    if not n:
        abort(404)
    broadcast(session["user"], "note", note_json(n))
    return jsonify(note_json(n))


@app.delete("/api/notes/<nid>")
def delete_note(nid):
    if not notes.delete_one({"_id": nid, "user": session["user"]}).deleted_count:
        abort(404)
    broadcast(session["user"], "gone", {"id": nid})
    return jsonify(ok=True)


# ---------- email a note (SMTP) ----------
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER
EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
EMAIL_LIMIT, EMAIL_WINDOW = 20, 3600  # per user per hour
sent_log: dict[str, list] = defaultdict(list)


@app.post("/api/notes/<nid>/email")
def email_note(nid):
    if not (SMTP_HOST and SMTP_FROM):
        return jsonify(error="Email isn't set up on the server (see SMTP_* in .env)"), 503
    me = users.find_one({"_id": session["user"]}, {"email": 1, "name": 1, "verified": 1}) or {}
    to = me.get("email", "")  # always the signed-in user's own Google address, never taken from the request
    if not me.get("verified") or len(to) > 254 or not EMAIL_RE.match(to):
        return jsonify(error="Sign in with Google to email notes to yourself"), 400
    n = notes.find_one({"_id": nid, "user": session["user"]})
    if not n:
        abort(404)
    now = time.time()
    log = sent_log[session["user"]] = [t for t in sent_log[session["user"]] if now - t < EMAIL_WINDOW]
    if len(log) >= EMAIL_LIMIT:
        return jsonify(error="Too many emails sent, try again later"), 429

    msg = EmailMessage()
    msg["Subject"] = " ".join((n["title"] or "Note").split())[:200]
    msg["From"] = f"{me.get('name') or 'CopeeMachine'} via CopeeMachine <{SMTP_FROM}>"
    msg["To"] = to
    title, body = n["title"].strip(), n["body"]
    msg.set_content("\n\n".join(x for x in (title, body, "Sent by CopeeMachine") if x))
    html_title = f"<b>{escape(title)}</b>" if title else ""
    msg.add_alternative(
        f'<div style="white-space:pre-wrap">{html_title}{"<br><br>" if title and body else ""}{escape(body)}<br><br>Sent by CopeeMachine</div>',
        subtype="html")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as e:
        app.logger.error("email send failed: %s", e)
        return jsonify(error="Couldn't send the email, check the server's SMTP settings"), 502
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


# ---------- built React app ----------
@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def spa(path):
    if path.startswith("api/"):
        abort(404)
    target = DIST / path
    if path and target.is_file() and DIST in target.resolve().parents:
        return send_from_directory(DIST, path)
    if not (DIST / "index.html").exists():
        return "Frontend not built. Run: cd frontend && npm run build", 503
    return send_from_directory(DIST, "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), threaded=True)
