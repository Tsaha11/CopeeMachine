# --- build the React app ---
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- run the Flask app ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 APP_ENV=production TRUST_PROXY=1 PORT=8080
WORKDIR /app
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist
RUN useradd -r -u 10001 app && mkdir -p data && chown app data
USER app
VOLUME /app/data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/healthz')"
CMD ["gunicorn", "-c", "backend/gunicorn.conf.py", "--chdir", "backend", "app:app"]
