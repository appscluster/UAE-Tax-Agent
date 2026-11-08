FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY agent /app/agent
COPY backend /app/backend
COPY data /app/data
COPY tests /app/tests
COPY pytest.ini /app/pytest.ini
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/tenant/readiness.db
ENV BACKUP_DIR=/data/backup
EXPOSE 8421
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8421"]
