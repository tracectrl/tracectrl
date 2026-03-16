FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# engine/ code uses `from engine.db.client import ...`
# Create a parent directory with engine/ symlinked so imports resolve correctly
RUN mkdir -p /opt/tracectrl && ln -s /app /opt/tracectrl/engine
ENV PYTHONPATH=/opt/tracectrl

CMD ["uvicorn", "engine.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Dev target (hot reload) ──────────────────────────
FROM base AS dev
RUN pip install --no-cache-dir watchfiles
CMD ["uvicorn", "engine.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
