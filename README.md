# CopeeMachine ☕

A Google-Keep-style notebook for text, images and files. Sign in with Google; every person gets
their own private notes, synced live across their phone and computer.
Flask backend (SQLite + files on disk) · React (Vite) frontend.

## 1. Get a Google Client ID (one time, free)
1. https://console.cloud.google.com → create/select a project.
2. **APIs & Services → OAuth consent screen**: External, fill app name + your email, publish.
3. **Credentials → Create credentials → OAuth client ID → Web application**.
4. **Authorized JavaScript origins**: add `http://localhost:5050` (and your real https URL when deployed).
5. Copy the Client ID into `.env` as `GOOGLE_CLIENT_ID`.

## 2. Run
```sh
cp .env.example .env                                   # paste GOOGLE_CLIENT_ID
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
.venv/bin/python backend/app.py                        # http://localhost:5050
```
Google sign-in only works on `localhost` or an https URL listed in step 1.

## Deploy (so phone + computer reach it from anywhere)
Run on any host with HTTPS, e.g. a small VPS/Fly/Render with:
`gunicorn -k gthread --threads 32 -w 1 -b 0.0.0.0:5050 --chdir backend app:app`
Set `COOKIE_SECURE=1` and add the https URL to the Google authorized origins.
Keep one worker (live-update connections are held in memory). Back up `./data`.

## Develop
`.venv/bin/python backend/app.py` + `cd frontend && npm run dev` (http://localhost:5173 proxies /api).
For testing without Google: `COPEE_DEV_LOGIN=1` shows a "Dev sign-in" button (never in production).
# CopeeMachine
# CopeeMachine
# CopeeMachine
