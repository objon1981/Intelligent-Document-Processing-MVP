FROM python:3.11-slim

# Install Tesseract and other dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Set the TESSDATA_PREFIX
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/

# Copy local Hausa/Yoruba/Igbo traineddata into the container
RUN mkdir -p /usr/share/tesseract-ocr/4.00/tessdata
COPY tessdata/*.traineddata /usr/share/tesseract-ocr/4.00/tessdata/

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8006

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8006"]
