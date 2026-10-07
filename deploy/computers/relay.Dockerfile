FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.34.2 httpx==0.28.1
COPY relay.py .
CMD ["uvicorn", "relay:app", "--host", "0.0.0.0", "--port", "4302", "--no-access-log"]
