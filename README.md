# CopeeMachine ☕

A Google-Keep-style notebook for text. Sign in with Google; every person gets their own private
notes, synced live across devices, and can email any note to themselves.

Two independent deployables in one repo:

| Folder | What | Stack |
|---|---|---|
| `backend/` | JSON API (auth, notes, live sync, email) | Flask · MongoDB · gunicorn |
| `frontend/` | Static web app | React (Vite) |

The frontend finds the API through `VITE_API_URL`; the API allows the frontend through `CORS_ORIGINS`.

## 1. Google sign-in (one time, free)
1. https://console.cloud.google.com → create/select a project.
2. **Google Auth Platform → Audience**: set **External** and **Publish app** (or add test users).
3. **Credentials → Create credentials → OAuth client ID → Web application**.
4. **Authorized JavaScript origins** = where the *frontend* is served: `http://localhost:5173` for dev
   and your frontend's `https://…` origin for production (no trailing slash or path).
   The backend's address does not go here.
5. Put the Client ID in `backend/.env` as `GOOGLE_CLIENT_ID`.

## 2. Email a note to yourself (SMTP)
The **Email** button sends to the Google address you signed in with, never to a typed address.
Gmail: enable 2-Step Verification, create an **App Password** (myaccount.google.com/apppasswords),
and set `SMTP_HOST/PORT/USER/PASSWORD`. Limit: 20 emails per user per hour.
Some hosts (including Render's free tier) block outbound SMTP ports; see Troubleshooting.

## 3. Run locally
```sh
cp backend/.env.example backend/.env                   # fill MONGODB_URI, GOOGLE_CLIENT_ID, SMTP_*
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/python backend/app.py                        # API on http://localhost:5050

cd frontend && npm install && npm run dev              # http://localhost:5173 (proxies /api to :5050)
```
No Google yet? Add `COPEE_DEV_LOGIN=1` to `backend/.env` for a "Dev sign-in" button (the Email button
is refused for dev users). The server refuses to start with it on in production.

## 4. Deploy the backend to Render
Prerequisites: a MongoDB Atlas cluster, and this repo pushed to GitHub.

1. **Atlas → Network Access**: allow `0.0.0.0/0` (Render's free tier has no fixed IP). Use a
   strong database password.
2. **Render → New → Blueprint** → pick this repo. It reads `render.yaml` and creates `copeemachine-api`.
3. Fill the prompted variables: `MONGODB_URI`, `GOOGLE_CLIENT_ID`, `SMTP_USER`, `SMTP_PASSWORD`,
   and `CORS_ORIGINS` (put a placeholder like `https://localhost` for now; set the real frontend
   origin after step 5).
4. After the deploy goes live, test it (replace the URL):
   ```sh
   curl https://copeemachine-api.onrender.com/healthz          # {"ok":true}
   curl https://copeemachine-api.onrender.com/api/config       # your clientId, "dev":false
   curl -i https://copeemachine-api.onrender.com/api/notes     # 401 Not logged in
   ```
   The free tier sleeps after ~15 minutes idle; the first request can take ~50 seconds.
5. Deploy the frontend (next section), then set `CORS_ORIGINS` to its origin and redeploy.

Variables the backend reads (see `backend/.env.example`): `APP_ENV=production`, `TRUST_PROXY=1`,
`SECRET_KEY`, `MONGODB_URI/DB`, `GOOGLE_CLIENT_ID`, `CORS_ORIGINS`, `COOKIE_SAMESITE`, `SMTP_*`.

**Docker instead:** `cd backend && docker build -t copeemachine-api . && docker run -p 8080:8080 --env-file .env -e COPEE_DEV_LOGIN= copeemachine-api`.

## 5. Deploy the frontend
Any static host (Render Static Site, Netlify, Cloudflare Pages, Vercel):
build command `npm ci && npm run build`, publish directory `frontend/dist`, root `frontend`,
env var `VITE_API_URL=https://<your-api-host>` (set at **build** time). Then add that site's
origin to Google's Authorized JavaScript origins and to the backend's `CORS_ORIGINS`.

**Cookies across sites:** two `*.onrender.com` hosts are different sites, so the login cookie is a
third-party cookie (`COOKIE_SAMESITE=None`, already set in `render.yaml`). Chrome allows it today;
Safari and some privacy settings block it. For a dependable setup put both on one domain
(`app.example.com` + `api.example.com`) and set `COOKIE_SAMESITE=Lax`.

## Troubleshooting
- **"Email couldn't be sent" on Render's free tier:** outbound SMTP ports (25/465/587) may be blocked there.
  Use a paid instance, or switch to an email provider's HTTPS API (Brevo, Resend, SendGrid).
- **Browser says CORS error:** the page's exact origin isn't in `CORS_ORIGINS`.
- **Signed in but immediately logged out:** the cookie is being blocked (see "Cookies across sites").
- **Google "origin not allowed":** the frontend origin is missing from Authorized JavaScript origins.
- Keep **one worker** (set in `gunicorn.conf.py`): live sync and rate limits live in memory.
- Never commit `.env`; rotate any secret that was pasted into a chat or ticket.
