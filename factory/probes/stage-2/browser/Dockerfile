# Probe runner image for dossier stage 2: Python + Playwright Chromium + axe-core (bundled by
# axe-playwright-python). Built with network access; run on the --internal probe network.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install --no-cache-dir "playwright==1.63.0" "axe-playwright-python==0.1.4" \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /probes
