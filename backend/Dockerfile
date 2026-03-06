# IMUSI Backend - production Dockerfile
# Build: docker build -t imusi-backend .
# Run (standalone): docker run -p 8000:8000 -e DATABASE_URL=... imusi-backend

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run uvicorn (override in docker-compose if needed)
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
