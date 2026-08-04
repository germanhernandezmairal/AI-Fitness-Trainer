FROM python:3.10-slim
WORKDIR /srv

# Librerías de sistema que OpenCV y MediaPipe necesitan para decodificar/
# escribir video y dibujar (no vienen en la imagen "slim" por defecto).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY security.py pipeline.py jobs.py main.py ./

EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
