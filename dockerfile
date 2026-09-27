FROM python:3.11-slim

# install GDAL & deps buat rasterio
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# set GDAL env
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV GDAL_VERSION=3.6.2

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# gradio port
EXPOSE 7860

# biar log langsung keluar
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
