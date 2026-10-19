"""One-time: authorize CopeeMachine to SEND email from your Gmail account and print a refresh token.

Run from the backend folder with the Flask server stopped (it uses port 5050 for the redirect):
    ../.venv/bin/python scripts/gmail_authorize.py
Needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env. The scope is gmail.send only:
the token can send mail but cannot read your inbox.
"""
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
PORT = 5050
REDIRECT = f"http://localhost:{PORT}"  # must be listed under the OAuth client's Authorized redirect URIs
if not (CLIENT_ID and CLIENT_SECRET):
    sys.exit("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env first")

state = secrets.token_urlsafe(16)
result = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get("state", [""])[0] == state and "code" in q:
            result["code"] = q["code"][0]
            msg = "Authorized. You can close this tab and return to the terminal."
        else:
            result["error"] = q.get("error", ["unexpected request"])[0]
            msg = f"Not authorized: {result['error']}"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode())
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *a):
        pass


url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
    "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "response_type": "code", "state": state,
    "scope": "https://www.googleapis.com/auth/gmail.send", "access_type": "offline", "prompt": "consent"})
server = HTTPServer(("127.0.0.1", PORT), Handler)
print("Opening your browser. Sign in with the Gmail account that should SEND the notes.\nIf it doesn't open, visit:\n" + url)
webbrowser.open(url)
server.serve_forever()

if "code" not in result:
    sys.exit(f"Authorization failed: {result.get('error')}")
r = requests.post("https://oauth2.googleapis.com/token", timeout=20, data={
    "code": result["code"], "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
d = r.json()
if "refresh_token" not in d:
    sys.exit(f"No refresh token returned: {d}")
print("\nSuccess. Set these on your server (Render -> Environment) and in backend/.env:\n")
print(f"GMAIL_REFRESH_TOKEN={d['refresh_token']}")
print("GMAIL_SENDER=<the Gmail address you just signed in with>")
print("GOOGLE_CLIENT_SECRET=<your OAuth client secret>")
print("\nTreat the refresh token like a password.")
