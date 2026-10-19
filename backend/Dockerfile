FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 APP_ENV=production TRUST_PROXY=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py gunicorn.conf.py ./
RUN useradd -r -u 10001 app && mkdir -p data && chown app data
USER app
VOLUME /app/data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/healthz')"
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
