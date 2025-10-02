FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
