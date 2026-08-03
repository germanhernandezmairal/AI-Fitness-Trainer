FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "httpx>=0.28" "python-multipart>=0.0.12"
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
