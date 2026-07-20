FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# libgomp1 required by PyTorch (Silero VAD used in Pipecat voice pipeline)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ .

# Default command
RUN chmod +x ./start.sh ./migrate.sh
CMD ["./start.sh"]

