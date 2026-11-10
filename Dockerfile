FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd -u 10001 -m aisx
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY aisx_os/ ./aisx_os/
COPY config/ ./config/
COPY static/ ./static/
RUN mkdir -p /app/data && chown -R aisx:aisx /app/data
USER aisx
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/healthz",timeout=3)' || exit 1
CMD ["uvicorn","aisx_os.api:app","--host","0.0.0.0","--port","8000","--workers","1"]
