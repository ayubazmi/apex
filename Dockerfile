FROM python:3.12-slim


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1



WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION} \
    APP_ENV=production

# Non-root user 
RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY app ./app
RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/ready', timeout=2).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
