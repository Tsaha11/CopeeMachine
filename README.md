# CopeeMachine ☕

A Google-Keep-style notebook for text. Sign in with Google; every person gets their own private
notes, synced live across their phone and computer, and can email any note to themselves.
Flask backend (MongoDB) · React (Vite) frontend.

## 1. Google sign-in (one time, free)
1. https://console.cloud.google.com → create/select a project.
2. **APIs & Services → OAuth consent screen**: External, fill app name + your email, then **Publish app**
   (while in "Testing", only listed test users can sign in).
3. **Credentials → Create credentials → OAuth client ID → Web application**.
4. **Authorized JavaScript origins**: add `http://localhost:5050` for local use and your real
   `https://your-domain` for production (exact origin, no trailing slash, no path).
5. Copy the Client ID into `.env` as `GOOGLE_CLIENT_ID`.

## 2. Email a note to yourself (SMTP)
The **Email** button sends the note to the Google address you signed in with (never to an address
typed in the browser). Gmail: turn on 2-Step Verification, create an **App Password** at
myaccount.google.com/apppasswords (16 letters, not your normal password), then set `SMTP_HOST`,
`SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` in `.env`. Limit: 20 emails per user per hour.

## 3. Run locally
```sh
cp .env.example .env                                   # fill in MONGODB_URI, GOOGLE_CLIENT_ID, SMTP_*
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
.venv/bin/python backend/app.py                        # http://localhost:5050
```
Dev: `.venv/bin/python backend/app.py` + `cd frontend && npm run dev` (http://localhost:5173 proxies /api).
Without Google: `COPEE_DEV_LOGIN=1` shows a "Dev sign-in" button (the Email button is disabled for
dev users). Never enable it in production; the server refuses to start if you do.

## 4. Production
Needs HTTPS (Google sign-in and secure cookies require it) and a MongoDB Atlas database.

**Environment variables on the host** (see `.env.example`):

| Variable | Value |
|---|---|
| `APP_ENV` | `production`: forces secure cookies, HSTS + CSP headers, blocks dev login |
| `TRUST_PROXY` | `1` when behind a reverse proxy / PaaS (nginx, Render, Fly, Railway…) |
| `MONGODB_URI`, `MONGODB_DB` | your Atlas connection |
| `GOOGLE_CLIENT_ID` | from step 1, with your https origin added |
| `SMTP_*` | from step 2 |
| `SECRET_KEY` | 64 random hex chars (`python3 -c "import secrets;print(secrets.token_hex(32))"`) so sessions survive redeploys on hosts without a persistent disk |

**Docker** (builds the frontend and runs gunicorn as a non-root user on port 8080):
```sh
docker build -t copeemachine .
docker run -p 8080:8080 --env-file .env -e APP_ENV=production -e TRUST_PROXY=1 -e COPEE_DEV_LOGIN= copeemachine
```
**Without Docker:** `cd frontend && npm ci && npm run build`, then
`APP_ENV=production TRUST_PROXY=1 gunicorn -c backend/gunicorn.conf.py --chdir backend app:app`.

**Notes**
- Keep **one worker** (already set): live-sync connections and the email rate limit live in memory.
  To scale past one instance, those need to move to Redis.
- Health check: `GET /healthz` (returns 503 if MongoDB is unreachable).
- In Atlas, allow your host's IP under Network Access.
- Don't commit `.env`; it's git-ignored. Rotate any secret that was ever pasted into a chat or ticket.
