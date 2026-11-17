FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app

# Providers are reached only through WebRouter (installed here, at build time, with its provider SDKs).
COPY requirements.txt .
RUN pip install --no-cache-dir "webrouter[search,extract,research]>=0.12.0" -r requirements.txt

COPY dossier/ dossier/
COPY tests/ tests/

EXPOSE 8080
CMD ["python", "-m", "dossier"]
